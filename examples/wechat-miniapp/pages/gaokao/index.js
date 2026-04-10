const { request } = require("../../utils/request");

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
    province: "吉林省",
    score: "",
    rank: "",
    subjectCombination: "",
    preferredMajors: "",
    preferredCities: "",
    careerPreferences: "",
    familyBudget: "",
    notes: "",
    planningStatus: "",
    planningError: "",
    recentPlans: [],
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token, province: "吉林省" });
    if (token) {
      this.loadRecentPlans();
    }
  },

  handleFieldInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [field]: event.detail.value });
  },

  async handleCreatePlan() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    if (!this.data.score || !this.data.subjectCombination) {
      wx.showToast({ title: "请先填写分数和选科", icon: "none" });
      return;
    }

    this.setData({ planningStatus: "processing", planningError: "" });
    try {
      wx.showLoading({ title: "生成方案中..." });
      const result = await request({
        url: "/gaokao/plan",
        method: "POST",
        token: this.data.token,
        timeout: 120000,
        data: {
          province: "吉林省",
          score: this.data.score.trim(),
          rank: this.data.rank.trim(),
          subject_combination: this.data.subjectCombination.trim(),
          preferred_majors: this.data.preferredMajors.trim(),
          preferred_cities: this.data.preferredCities.trim(),
          career_preferences: this.data.careerPreferences.trim(),
          family_budget: this.data.familyBudget.trim(),
          notes: this.data.notes.trim(),
        },
      });

      this.setData({ planningStatus: "completed" });
      this.loadRecentPlans();
      wx.navigateTo({ url: `/pages/gaokao-result/index?planId=${result.plan_id}` });
    } catch (error) {
      const message = getErrorMessage(error, "生成失败");
      console.error(error);
      this.setData({ planningStatus: "failed", planningError: message });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  async loadRecentPlans() {
    try {
      const recentPlans = await request({
        url: "/gaokao",
        method: "GET",
        token: this.data.token,
        timeout: 30000,
      });
      this.setData({ recentPlans: recentPlans || [] });
    } catch (error) {
      console.error(error);
    }
  },

  openPlanDetail(event) {
    const planId = event.currentTarget.dataset.planId;
    if (!planId) return;
    wx.navigateTo({ url: `/pages/gaokao-result/index?planId=${planId}` });
  },
});
