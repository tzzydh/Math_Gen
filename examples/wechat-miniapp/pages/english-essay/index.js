const { request } = require("../../utils/request");

function chooseEssayImage() {
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
  if (error.statusCode) return `Request failed (${error.statusCode})`;
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
    uploading: false,
    reviewing: false,
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token });
  },

  async handleChooseEssayAndUpload() {
    if (!this.data.token) {
      wx.showToast({ title: "Please log in first", icon: "none" });
      return;
    }
    if (this.data.uploading) {
      return;
    }

    let loadingShown = false;
    this.setData({ uploading: true });
    try {
      const file = await chooseEssayImage();
      wx.showLoading({ title: "Uploading..." });
      loadingShown = true;

      const presign = await request({
        url: "/uploads/presign",
        method: "POST",
        token: this.data.token,
        data: {
          filename: file.name,
          content_type: file.mimeType,
          directory: "essay-screenshots/english",
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

      wx.showToast({ title: "Upload complete", icon: "success" });
    } catch (error) {
      if (isUserCancelled(error)) {
        return;
      }
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "Upload failed"), icon: "none" });
    } finally {
      this.setData({ uploading: false });
      if (loadingShown) {
        wx.hideLoading();
      }
    }
  },

  async handleRunEssayCorrection() {
    if (!this.data.essayAssetId) {
      wx.showToast({ title: "Upload essay first", icon: "none" });
      return;
    }
    if (this.data.reviewing) {
      return;
    }

    let loadingShown = false;
    this.setData({
      essayStatus: "processing",
      essayError: "",
      reviewing: true,
    });

    try {
      wx.showLoading({ title: "Reviewing..." });
      loadingShown = true;

      const payload = {
        asset_id: this.data.essayAssetId,
        subject: "english",
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
      wx.navigateTo({
        url: `/pages/essay-result/index?reviewId=${result.review_id}`,
      });
    } catch (error) {
      console.error(error);
      const message = getErrorMessage(error, "Review failed");
      this.setData({
        essayStatus: "failed",
        essayError: message,
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      this.setData({ reviewing: false });
      if (loadingShown) {
        wx.hideLoading();
      }
    }
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
