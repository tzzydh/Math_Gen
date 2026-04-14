const { request } = require("../../utils/request");

const DEFAULT_PROVINCE = "\u5409\u6797\u7701";

const ADVISOR_MODE_OPTIONS = [
  { label: "混合增强", value: "hybrid" },
  { label: "纯规则模式", value: "rules_only" },
];

const ADVISOR_PROVIDER_OPTIONS = [
  { label: "Gemini", value: "gemini" },
  { label: "GLM / 智谱兼容接口", value: "glm" },
  { label: "OpenAI", value: "openai" },
];

const ADVISOR_MODEL_OPTIONS_BY_PROVIDER = {
  gemini: [
    { label: "系统默认", value: "" },
    { label: "gemini-2.5-flash", value: "gemini-2.5-flash" },
    { label: "gemini-2.5-pro", value: "gemini-2.5-pro" },
  ],
  glm: [
    { label: "系统默认", value: "" },
    { label: "GLM-4.5V", value: "GLM-4.5V" },
    { label: "GLM-4.5-Air", value: "GLM-4.5-Air" },
    { label: "GLM-4.5", value: "GLM-4.5" },
  ],
  openai: [
    { label: "系统默认", value: "" },
    { label: "gpt-4o-mini", value: "gpt-4o-mini" },
    { label: "gpt-4.1-mini", value: "gpt-4.1-mini" },
  ],
};

const STEP_OPTIONS = [
  { key: "basic", label: "基础建档", caption: "分数 / 位次 / 选科" },
  { key: "consult", label: "顾问问诊", caption: "追问关键条件" },
  { key: "final", label: "最终方案", caption: "模式 / 偏好 / 生成报告" },
];

function getErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  if (error.errMsg) return error.errMsg;
  return fallback;
}

function normalizeRankValue(value) {
  const text = String(value || "").trim();
  const matched = text.match(/\d+/);
  return matched ? matched[0] : "";
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

Page({
  data: {
    token: "",
    province: DEFAULT_PROVINCE,
    activeModule: "basic",
    stepOptions: STEP_OPTIONS,
    score: "",
    rank: "",
    subjectCombination: "",
    preferredMajors: "",
    preferredCities: "",
    careerPreferences: "",
    familyBudget: "",
    notes: "",
    advisorMode: "hybrid",
    advisorProvider: "gemini",
    advisorModel: "",
    advisorModeOptions: ADVISOR_MODE_OPTIONS,
    advisorProviderOptions: ADVISOR_PROVIDER_OPTIONS,
    advisorModelOptions: ADVISOR_MODEL_OPTIONS_BY_PROVIDER.gemini,
    consultStatus: "",
    consultError: "",
    consultation: null,
    planningStatus: "",
    planningError: "",
    consulting: false,
    creatingPlan: false,
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({
      token,
      province: DEFAULT_PROVINCE,
    });
  },

  getFieldValue(field) {
    const fieldMap = {
      score: this.data.score,
      rank: this.data.rank,
      subjectCombination: this.data.subjectCombination,
      preferredMajors: this.data.preferredMajors,
      preferredCities: this.data.preferredCities,
      careerPreferences: this.data.careerPreferences,
      familyBudget: this.data.familyBudget,
      notes: this.data.notes,
      subject_combination: this.data.subjectCombination,
      preferred_majors: this.data.preferredMajors,
      preferred_cities: this.data.preferredCities,
      career_preferences: this.data.careerPreferences,
      family_budget: this.data.familyBudget,
    };
    return fieldMap[field] || "";
  },

  decorateConsultation(consultation) {
    if (!consultation) return null;
    const questions = (consultation.questions || []).map((question) => ({
      ...question,
      currentValue: this.getFieldValue(question.field),
    }));
    const requiredQuestions = questions.filter((question) => question.required);
    const answeredRequired = requiredQuestions.filter((question) =>
      String(question.currentValue || "").trim()
    ).length;
    return {
      ...consultation,
      questions,
      requiredCount: requiredQuestions.length,
      answeredRequired,
      completionText:
        requiredQuestions.length > 0
          ? `${answeredRequired}/${requiredQuestions.length} 必答已完成`
          : "当前没有必答项",
    };
  },

  handleModuleTap(event) {
    const moduleKey = event.currentTarget.dataset.module;
    if (!moduleKey) return;
    this.setData({ activeModule: moduleKey });
  },

  handleFieldInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({
      [field]: event.detail.value,
      consultError: "",
      planningError: "",
      consultation: this.decorateConsultation(this.data.consultation),
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
      consultation: this.decorateConsultation(this.data.consultation),
    });
  },

  handleAdvisorModeTap(event) {
    this.setData({ advisorMode: event.currentTarget.dataset.value });
  },

  handleAdvisorProviderTap(event) {
    const provider = event.currentTarget.dataset.value;
    this.setData({
      advisorProvider: provider,
      advisorModel: "",
      advisorModelOptions:
        ADVISOR_MODEL_OPTIONS_BY_PROVIDER[provider] || ADVISOR_MODEL_OPTIONS_BY_PROVIDER.gemini,
    });
  },

  handleAdvisorModelTap(event) {
    this.setData({ advisorModel: event.currentTarget.dataset.value });
  },

  handleConfirmConsultation() {
    const consultation = this.data.consultation;
    if (!consultation) {
      wx.showToast({ title: "请先生成顾问问诊", icon: "none" });
      return;
    }

    const unanswered = (consultation.questions || []).filter(
      (question) => question.required && !String(question.currentValue || "").trim()
    );
    if (unanswered.length > 0) {
      wx.showToast({
        title: `还有 ${unanswered.length} 个必答项未完成`,
        icon: "none",
      });
      return;
    }

    this.setData({ activeModule: "final" });
    wx.showToast({ title: "已确认，继续生成方案", icon: "success" });
  },

  buildPayload() {
    return {
      province: DEFAULT_PROVINCE,
      score: (this.data.score || "").trim(),
      rank: normalizeRankValue(this.data.rank),
      subject_combination: (this.data.subjectCombination || "").trim(),
      preferred_majors: (this.data.preferredMajors || "").trim(),
      preferred_cities: (this.data.preferredCities || "").trim(),
      career_preferences: (this.data.careerPreferences || "").trim(),
      family_budget: (this.data.familyBudget || "").trim(),
      notes: (this.data.notes || "").trim(),
      advisor_mode: this.data.advisorMode,
      advisor_provider: this.data.advisorProvider,
      advisor_model: (this.data.advisorModel || "").trim() || undefined,
    };
  },

  handleUnauthorized() {
    wx.removeStorageSync("access_token");
    wx.removeStorageSync("user_profile");
    this.setData({ token: "" });
    wx.showToast({ title: "登录已失效，请重新登录", icon: "none" });
  },

  async handleStartConsultation() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    if (this.data.consulting) {
      return;
    }

    let loadingShown = false;
    this.setData({
      consultStatus: "processing",
      consultError: "",
      consultation: null,
      consulting: true,
    });

    try {
      loadingShown = showLoading("顾问问诊中...");
      const result = await request({
        url: "/gaokao/consultation",
        method: "POST",
        token: this.data.token,
        timeout: 30000,
        data: this.buildPayload(),
      });

      if (!result || !result.readiness) {
        throw new Error("问诊结果为空，请重试");
      }

      this.setData({
        consultation: this.decorateConsultation(result),
        consultStatus: result.readiness,
        activeModule: result.readiness === "ready" ? "final" : "consult",
      });

      hideLoadingIfNeeded(loadingShown);
      loadingShown = false;
      wx.showToast({
        title: result.readiness === "ready" ? "可以直接生成方案" : "已生成顾问追问",
        icon: "success",
      });
    } catch (error) {
      const message = getErrorMessage(error, "问诊失败");
      console.error(error);
      if (message.includes("invalid access token")) {
        this.handleUnauthorized();
      }
      this.setData({
        consultStatus: "failed",
        consultError: message,
        activeModule: "basic",
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      this.setData({ consulting: false });
      hideLoadingIfNeeded(loadingShown);
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
    if (this.data.creatingPlan) {
      return;
    }

    let loadingShown = false;
    this.setData({
      planningStatus: "processing",
      planningError: "",
      creatingPlan: true,
    });

    try {
      loadingShown = showLoading("生成方案中...");
      const result = await request({
        url: "/gaokao/plan",
        method: "POST",
        token: this.data.token,
        timeout: 180000,
        data: this.buildPayload(),
      });

      this.setData({ planningStatus: "completed" });
      hideLoadingIfNeeded(loadingShown);
      loadingShown = false;
      wx.navigateTo({
        url: `/pages/gaokao-result/index?planId=${result.plan_id}`,
      });
    } catch (error) {
      const message = getErrorMessage(error, "生成失败");
      console.error(error);
      if (message.includes("invalid access token")) {
        this.handleUnauthorized();
      }
      this.setData({
        planningStatus: "failed",
        planningError: message,
        activeModule: "final",
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      this.setData({ creatingPlan: false });
      hideLoadingIfNeeded(loadingShown);
    }
  },
});
