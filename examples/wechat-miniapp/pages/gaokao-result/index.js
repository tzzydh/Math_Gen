const { request } = require("../../utils/request");
const { buildApiUrl } = require("../../utils/config");

const TRACK_LABELS = {
  physics: "物理类",
  history: "历史类",
};

const LINE_LABELS = {
  special: "特控线",
  undergraduate: "本科线",
  specialty: "专科线",
};

const BUCKET_LABELS = {
  chong: "冲",
  wen: "稳",
  bao: "保",
};

const BUCKET_TITLES = {
  chong: "冲一冲",
  wen: "稳一稳",
  bao: "保一保",
};

function getErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  if (error.errMsg) return error.errMsg;
  return fallback;
}

Page({
  data: {
    token: "",
    planId: "",
    result: null,
    loading: true,
    error: "",
    downloading: false,
  },

  onLoad(options) {
    this.setData({ planId: options.planId || "" });
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token });
    if (token && this.data.planId) {
      this.loadPlanDetail();
    }
  },

  async loadPlanDetail() {
    this.setData({ loading: true, error: "" });
    try {
      const result = await request({
        url: `/gaokao/${this.data.planId}`,
        method: "GET",
        token: this.data.token,
        timeout: 30000,
      });

      const recommendations = (result.recommendations || []).map((item) => ({
        ...item,
        bucketLabel: BUCKET_LABELS[item.bucket] || item.bucket,
      }));
      const controlLines = (result.control_lines || []).map((item) => ({
        ...item,
        label: LINE_LABELS[item.line_type] || item.line_type,
      }));

      this.setData({
        loading: false,
        result: {
          ...result,
          trackLabel: TRACK_LABELS[result.track] || result.track,
          controlLines,
          bucketGroups: this.groupByBucket(recommendations),
          recommendationCount: recommendations.length,
        },
      });
    } catch (error) {
      console.error(error);
      this.setData({
        loading: false,
        error: getErrorMessage(error, "结果加载失败"),
      });
    }
  },

  groupByBucket(recommendations) {
    return ["chong", "wen", "bao"]
      .map((key) => ({
        key,
        title: BUCKET_TITLES[key],
        items: recommendations.filter((item) => item.bucket === key),
      }))
      .filter((section) => section.items.length);
  },

  async handleDownloadPlanPdf() {
    if (!this.data.planId || !this.data.token) {
      wx.showToast({ title: "请先登录后重试", icon: "none" });
      return;
    }
    if (this.data.downloading) {
      return;
    }

    const downloadUrl = buildApiUrl(`/gaokao/${this.data.planId}/pdf-download`);
    let loadingShown = false;
    this.setData({ downloading: true });
    try {
      console.log("wx.downloadFile ->", downloadUrl);
      wx.showLoading({ title: "下载报告中..." });
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

      wx.showToast({ title: "报告已打开", icon: "success" });
    } catch (error) {
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "下载失败"), icon: "none" });
    } finally {
      this.setData({ downloading: false });
      if (loadingShown) {
        wx.hideLoading();
      }
    }
  },
});
