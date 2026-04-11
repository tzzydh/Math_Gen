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
    consultStatus: "",
    consultError: "",
    consultation: null,
    planningStatus: "",
    planningError: "",
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({
      token,
      province: "吉林省",
    });
  },

  handleFieldInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({
      [field]: event.detail.value,
      consultError: "",
      planningError: "",
    });
  },

  handleQuestionOptionTap(event) {
    const field = event.currentTarget.dataset.field;
    const value = event.currentTarget.dataset.value;
    if (!field) return;
    this.setData({
      [field]: value,
      consultError: "",
      planningError: "",
    });
  },

  buildPayload() {
    return {
      province: "吉林省",
      score: (this.data.score || "").trim(),
      rank: (this.data.rank || "").trim(),
      subject_combination: (this.data.subjectCombination || "").trim(),
      preferred_majors: (this.data.preferredMajors || "").trim(),
      preferred_cities: (this.data.preferredCities || "").trim(),
      career_preferences: (this.data.careerPreferences || "").trim(),
      family_budget: (this.data.familyBudget || "").trim(),
      notes: (this.data.notes || "").trim(),
    };
  },

  async handleStartConsultation() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }

    let loadingShown = false;
    this.setData({
      consultStatus: "processing",
      consultError: "",
      consultation: null,
    });
    try {
      wx.showLoading({ title: "顾问问诊中..." });
      loadingShown = true;
      const result = await request({
        url: "/gaokao/consultation",
        method: "POST",
        token: this.data.token,
        timeout: 30000,
        data: this.buildPayload(),
      });
      this.setData({
        consultation: result,
        consultStatus: result.readiness,
      });
      wx.showToast({
        title: result.readiness === "ready" ? "可以生成方案了" : "已生成追问",
        icon: "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "问诊失败");
      console.error(error);
      this.setData({
        consultStatus: "failed",
        consultError: message,
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      if (loadingShown) {
        wx.hideLoading();
      }
    }
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

    let loadingShown = false;
    this.setData({ planningStatus: "processing", planningError: "" });
    try {
      wx.showLoading({ title: "生成方案中..." });
      loadingShown = true;
      const result = await request({
        url: "/gaokao/plan",
        method: "POST",
        token: this.data.token,
        timeout: 120000,
        data: this.buildPayload(),
      });

      this.setData({ planningStatus: "completed" });
      wx.navigateTo({
        url: `/pages/gaokao-result/index?planId=${result.plan_id}`,
      });
    } catch (error) {
      const message = getErrorMessage(error, "生成失败");
      console.error(error);
      this.setData({
        planningStatus: "failed",
        planningError: message,
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      if (loadingShown) {
        wx.hideLoading();
      }
    }
  },
});
