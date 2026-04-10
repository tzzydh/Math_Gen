function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: resolve,
      fail: reject,
    });
  });
}

function getErrorMessage(error, fallback) {
  if (!error) {
    return fallback;
  }
  if (typeof error === "string") {
    return error;
  }
  if (error.detail) {
    return error.detail;
  }
  if (error.errMsg) {
    return error.errMsg;
  }
  return fallback;
}

Page({
  data: {
    token: "",
    userLabel: "未登录",
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    const user = wx.getStorageSync("user_profile") || null;
    this.setData({
      token,
      userLabel: user?.nickname || "未登录",
    });
  },

  async handleWechatLogin() {
    try {
      const loginRes = await wxLogin();
      const profile = await this.getMiniProfile();
      const { request } = require("../../utils/request");
      const result = await request({
        url: "/auth/wechat/login",
        method: "POST",
        data: {
          code: loginRes.code,
          nickname: profile.nickName,
          avatar_url: profile.avatarUrl,
        },
      });

      wx.setStorageSync("access_token", result.access_token);
      wx.setStorageSync("user_profile", result.user || {});
      this.setData({
        token: result.access_token,
        userLabel: result.user?.nickname || profile.nickName || "已登录用户",
      });
      wx.showToast({ title: "登录成功", icon: "success" });
    } catch (error) {
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "登录失败"), icon: "none" });
    }
  },

  goMathPage() {
    wx.navigateTo({ url: "/pages/math/index" });
  },

  goChineseEssayPage() {
    wx.navigateTo({ url: "/pages/essay/index" });
  },

  goEnglishEssayPage() {
    wx.navigateTo({ url: "/pages/english-essay/index" });
  },

  goGaokaoPage() {
    wx.navigateTo({ url: "/pages/gaokao/index" });
  },

  getMiniProfile() {
    return new Promise((resolve) => {
      wx.getUserProfile({
        desc: "用于生成更个性化的学习诊断与报告展示",
        success(res) {
          resolve(res.userInfo || {});
        },
        fail() {
          resolve({});
        },
      });
    });
  },
});
