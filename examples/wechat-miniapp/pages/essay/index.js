const { request } = require("../../utils/request");

function wxChooseEssayImage() {
  return new Promise((resolve, reject) => {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album", "camera"],
      success(res) {
        const filePath = res.tempFilePaths?.[0];
        const fileMeta = res.tempFiles?.[0] || {};
        if (!filePath) {
          reject({ errMsg: "chooseImage:fail no file selected" });
          return;
        }
        resolve({
          tempFilePath: filePath,
          size: fileMeta.size || 0,
          mimeType: inferMimeType(filePath),
          name: filePath.split("/").pop(),
        });
      },
      fail: reject,
    });
  });
}

function inferMimeType(filePath) {
  const lower = (filePath || "").toLowerCase();
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  return "image/png";
}

function getErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error.detail) return error.detail;
  if (error.errMsg) return error.errMsg;
  if (error.statusCode) return `请求失败(${error.statusCode})`;
  return fallback;
}

function isUserCancelled(error) {
  const errMsg = error?.errMsg || "";
  return typeof errMsg === "string" && errMsg.includes("cancel");
}

Page({
  data: {
    token: "",
    essayAssetId: null,
    essayUploadedUrl: "",
    essayTitle: "",
    essayRawText: "",
    essayStatus: "",
    essayError: "",
    recentReviews: [],
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token });
    if (token) {
      this.loadRecentReviews();
    }
  },

  async handleChooseEssayAndUpload() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }

    try {
      const file = await wxChooseEssayImage();
      wx.showLoading({ title: "上传中..." });

      const presign = await request({
        url: "/uploads/presign",
        method: "POST",
        token: this.data.token,
        data: {
          filename: file.name,
          content_type: file.mimeType,
          directory: "essay-screenshots/chinese",
        },
      });

      await this.uploadToOss(file.tempFilePath, presign);

      const confirm = await request({
        url: "/uploads/confirm",
        method: "POST",
        token: this.data.token,
        data: {
          asset_id: presign.asset_id,
          size: file.size,
          mime_type: file.mimeType,
        },
      });

      this.setData({
        essayAssetId: confirm.asset_id,
        essayUploadedUrl: confirm.public_url,
        essayStatus: "",
        essayError: "",
      });

      wx.showToast({ title: "上传成功", icon: "success" });
    } catch (error) {
      if (isUserCancelled(error)) return;
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "上传失败"), icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  async handleRunEssayCorrection() {
    if (!this.data.essayAssetId) {
      wx.showToast({ title: "请先上传作文截图", icon: "none" });
      return;
    }

    this.setData({ essayStatus: "processing", essayError: "" });

    try {
      wx.showLoading({ title: "批改中..." });
      const payload = {
        asset_id: this.data.essayAssetId,
        subject: "chinese",
      };
      if (this.data.essayTitle && this.data.essayTitle.trim()) {
        payload.title = this.data.essayTitle.trim();
      }
      if (this.data.essayRawText && this.data.essayRawText.trim()) {
        payload.raw_text = this.data.essayRawText.trim();
      }

      const result = await request({
        url: "/essays/correct",
        method: "POST",
        token: this.data.token,
        data: payload,
        timeout: 180000,
      });

      this.setData({ essayStatus: "completed" });
      this.loadRecentReviews();
      wx.navigateTo({ url: `/pages/essay-result/index?reviewId=${result.review_id}` });
    } catch (error) {
      console.error(error);
      const message = getErrorMessage(error, "批改失败");
      this.setData({ essayStatus: "failed", essayError: message });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  async loadRecentReviews() {
    try {
      const recentReviews = await request({
        url: "/essays?subject=chinese",
        method: "GET",
        token: this.data.token,
        timeout: 30000,
      });
      this.setData({ recentReviews: recentReviews || [] });
    } catch (error) {
      console.error(error);
    }
  },

  openReviewDetail(event) {
    const reviewId = event.currentTarget.dataset.reviewId;
    if (!reviewId) return;
    wx.navigateTo({ url: `/pages/essay-result/index?reviewId=${reviewId}` });
  },

  handleEssayTitleInput(event) {
    this.setData({ essayTitle: event.detail.value });
  },

  handleEssayRawTextInput(event) {
    this.setData({ essayRawText: event.detail.value });
  },

  uploadToOss(filePath, presign) {
    return new Promise((resolve, reject) => {
      wx.uploadFile({
        url: presign.upload_host,
        filePath,
        name: "file",
        formData: presign.form_data,
        success(res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res);
            return;
          }
          reject(res);
        },
        fail: reject,
      });
    });
  },
});
