const { request } = require("../../utils/request");
const { buildApiUrl } = require("../../utils/config");

function getSubjectLabel(subject) {
  return subject === "english" ? "英语作文" : "语文作文";
}

function getErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  if (error.errMsg) return error.errMsg;
  if (error.statusCode) return `请求失败(${error.statusCode})`;
  return fallback;
}

function joinList(items) {
  return (items || []).join("；");
}

function showLoading(title) {
  wx.showLoading({ title, mask: true });
  return true;
}

function hideLoadingIfNeeded(flag) {
  if (flag) {
    wx.hideLoading();
  }
}

function saveTempFile(tempFilePath) {
  return new Promise((resolve, reject) => {
    const fs = wx.getFileSystemManager();
    const fileName = `essay-review-${Date.now()}.pdf`;
    const targetPath = `${wx.env.USER_DATA_PATH}/${fileName}`;
    fs.saveFile({
      tempFilePath,
      filePath: targetPath,
      success: resolve,
      fail: reject,
    });
  });
}

Page({
  data: {
    token: "",
    reviewId: "",
    result: null,
    subjectLabel: "",
    strengthsText: "",
    issuesText: "",
    suggestionsText: "",
    strengthsCnText: "",
    issuesCnText: "",
    suggestionsCnText: "",
    isEnglish: false,
    loading: true,
    error: "",
    downloading: false,
  },

  onLoad(options) {
    this.setData({ reviewId: options.reviewId || "" });
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token });
    if (token && this.data.reviewId) {
      this.loadReviewDetail();
    }
  },

  async loadReviewDetail() {
    this.setData({ loading: true, error: "" });
    try {
      const result = await request({
        url: `/essays/${this.data.reviewId}`,
        method: "GET",
        token: this.data.token,
        timeout: 30000,
      });

      const isEnglish = result.subject === "english";
      this.setData({
        result,
        isEnglish,
        subjectLabel: getSubjectLabel(result.subject),
        strengthsText: joinList(result.strengths),
        issuesText: joinList(result.issues),
        suggestionsText: joinList(result.suggestions),
        strengthsCnText: joinList(result.strengths_cn),
        issuesCnText: joinList(result.issues_cn),
        suggestionsCnText: joinList(result.suggestions_cn),
        loading: false,
      });
    } catch (error) {
      console.error(error);
      this.setData({
        loading: false,
        error: getErrorMessage(error, "结果加载失败"),
      });
    }
  },

  async handleDownloadEssayPdf() {
    if (!this.data.reviewId || !this.data.token) {
      wx.showToast({ title: "请先登录后重试", icon: "none" });
      return;
    }
    if (this.data.downloading) {
      return;
    }

    const downloadUrl = buildApiUrl(`/essays/${this.data.reviewId}/pdf-download`);
    let loadingShown = false;
    this.setData({ downloading: true });
    try {
      console.log("wx.downloadFile ->", downloadUrl);
      loadingShown = showLoading("下载 PDF...");

      const downloadRes = await new Promise((resolve, reject) => {
        wx.downloadFile({
          url: downloadUrl,
          header: {
            Authorization: `Bearer ${this.data.token}`,
          },
          success: resolve,
          fail: reject,
        });
      });

      if (!(downloadRes.statusCode >= 200 && downloadRes.statusCode < 300)) {
        throw downloadRes;
      }

      const savedFile = await saveTempFile(downloadRes.tempFilePath).catch(() => ({
        savedFilePath: downloadRes.tempFilePath,
      }));

      hideLoadingIfNeeded(loadingShown);
      loadingShown = false;

      await new Promise((resolve, reject) => {
        wx.openDocument({
          filePath: savedFile.savedFilePath || downloadRes.tempFilePath,
          fileType: "pdf",
          showMenu: true,
          success: resolve,
          fail: reject,
        });
      });

      wx.showToast({ title: "PDF 已打开", icon: "success" });
    } catch (error) {
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "PDF 下载失败"), icon: "none" });
    } finally {
      this.setData({ downloading: false });
      hideLoadingIfNeeded(loadingShown);
    }
  },

  copyPdfLink() {
    if (!this.data.reviewId) {
      wx.showToast({ title: "暂无链接", icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: buildApiUrl(`/essays/${this.data.reviewId}/pdf-download`),
    });
  },
});
