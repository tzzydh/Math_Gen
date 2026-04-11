const { request } = require("../../utils/request");
const { getApiBaseUrl } = require("../../utils/config");

function getSubjectLabel(subject) {
  if (subject === "english") {
    return "英语作文";
  }
  return "语文作文";
}

function getErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  if (error.errMsg) return error.errMsg;
  if (error.statusCode) return `请求失败(${error.statusCode})`;
  return fallback;
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
    loading: true,
    error: "",
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
      this.setData({
        result,
        subjectLabel: getSubjectLabel(result.subject),
        strengthsText: (result.strengths || []).join("；"),
        issuesText: (result.issues || []).join("；"),
        suggestionsText: (result.suggestions || []).join("；"),
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

    const downloadUrl = `${getApiBaseUrl()}/essays/${this.data.reviewId}/pdf-download`;
    let loadingShown = false;
    try {
      wx.showLoading({ title: "下载 PDF..." });
      loadingShown = true;

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

      const savedFile = await new Promise((resolve, reject) => {
        wx.saveFile({
          tempFilePath: downloadRes.tempFilePath,
          success: resolve,
          fail: reject,
        });
      }).catch(() => ({ savedFilePath: downloadRes.tempFilePath }));

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
      if (loadingShown) {
        wx.hideLoading();
      }
    }
  },

  copyPdfLink() {
    if (!this.data.reviewId) {
      wx.showToast({ title: "暂无链接", icon: "none" });
      return;
    }
    wx.setClipboardData({ data: `${getApiBaseUrl()}/essays/${this.data.reviewId}/pdf-download` });
  },
});
