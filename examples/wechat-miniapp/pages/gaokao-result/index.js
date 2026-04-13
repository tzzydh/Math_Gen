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

function getAdvisorProviderLabel(provider) {
  if (provider === "gemini") return "Gemini";
  if (provider === "openai") return "OpenAI";
  if (provider === "glm") return "GLM / 智谱兼容接口";
  return "系统默认";
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
        rankingReasonText: (item.ranking_reasons || []).join("、"),
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
          majorProfile: result.major_profile || null,
          majorBreakdown: result.major_breakdown || [],
          signatureAdvice: result.signature_advice || [],
          schoolPoolNote: result.school_pool_note || "",
          extendedPoolGroups: this.groupExtendedPool(result.extended_pool || []),
          recommendationCount: recommendations.length,
          advisorModeLabel: result.llm_enhanced ? "规则打底 + 模型增强" : "纯规则模式",
          advisorProviderLabel: getAdvisorProviderLabel(result.advisor_provider),
          advisorModelLabel: result.advisor_model || "未启用",
          advisorEngineNote: result.advisor_engine_note || "",
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

  groupExtendedPool(items) {
    const groups = {};
    items.forEach((item) => {
      const key = item.group || "方向扩展池";
      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push(item);
    });
    return Object.keys(groups).map((key) => ({
      key,
      title: key,
      items: groups[key],
    }));
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
        const fs = wx.getFileSystemManager();
        fs.saveFile({
          tempFilePath: downloadRes.tempFilePath,
          filePath: `${wx.env.USER_DATA_PATH}/gaokao-plan-${this.data.planId}.pdf`,
          success: resolve,
          fail: reject,
        });
      }).catch(() => ({ savedFilePath: downloadRes.tempFilePath }));

      if (loadingShown) {
        wx.hideLoading();
        loadingShown = false;
      }

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
