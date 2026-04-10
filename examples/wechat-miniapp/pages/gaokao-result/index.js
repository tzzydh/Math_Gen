const { request } = require("../../utils/request");

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
          recommendations,
          bucketGroups: this.groupByBucket(recommendations),
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
    const sections = [
      { key: "chong", title: "冲一冲", items: [] },
      { key: "wen", title: "稳一稳", items: [] },
      { key: "bao", title: "保一保", items: [] },
    ];
    sections.forEach((section) => {
      section.items = recommendations.filter((item) => item.bucket === section.key);
    });
    return sections.filter((section) => section.items.length);
  },
});
