const { request } = require("../../utils/request");

function wxChooseMedia() {
  return new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
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

function isUserCancelled(error) {
  const errMsg = error?.errMsg || "";
  return typeof errMsg === "string" && errMsg.includes("cancel");
}

Page({
  data: {
    token: "",
    assetId: null,
    uploadedUrl: "",
    rawText: "",
    diagnosticId: null,
    diagnosticStatus: "",
    diagnosticResult: null,
    diagnosticError: "",
    diagnosticKnowledgeText: "",
    diagnosticTopMatchesText: "",
  },

  onShow() {
    const token = wx.getStorageSync("access_token") || "";
    this.setData({ token });
  },

  async handleChooseAndUpload() {
    try {
      const chooseRes = await wxChooseMedia();
      const file = chooseRes.tempFiles[0];
      wx.showLoading({ title: "上传中..." });

      const presign = await request({
        url: "/uploads/presign",
        method: "POST",
        token: this.data.token,
        data: {
          filename: file.originalFileObj?.name || file.tempFilePath.split("/").pop(),
          content_type: file.mimeType || "image/jpeg",
          directory: "questions",
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
          mime_type: file.mimeType || "image/jpeg",
        },
      });

      this.setData({
        assetId: confirm.asset_id,
        uploadedUrl: confirm.public_url,
        diagnosticId: null,
        diagnosticStatus: "",
        diagnosticResult: null,
        diagnosticError: "",
        diagnosticKnowledgeText: "",
        diagnosticTopMatchesText: "",
      });
      wx.showToast({ title: "上传成功", icon: "success" });
    } catch (error) {
      if (isUserCancelled(error)) {
        return;
      }
      console.error(error);
      wx.showToast({ title: getErrorMessage(error, "上传失败"), icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  async handleRunDiagnostic() {
    if (!this.data.assetId) {
      wx.showToast({ title: "请先上传题目", icon: "none" });
      return;
    }

    this.setData({
      diagnosticStatus: "processing",
      diagnosticError: "",
      diagnosticResult: null,
      diagnosticKnowledgeText: "",
      diagnosticTopMatchesText: "",
    });

    try {
      wx.showLoading({ title: "诊断中..." });
      const payload = {
        asset_id: this.data.assetId,
      };
      if (this.data.rawText && this.data.rawText.trim()) {
        payload.raw_text = this.data.rawText.trim();
      }

      const result = await request({
        url: "/diagnostics",
        method: "POST",
        token: this.data.token,
        data: payload,
        timeout: 120000,
      });

      this.setData({
        diagnosticId: result.id,
        diagnosticStatus: result.status,
        diagnosticResult: result.result,
        diagnosticError: result.error_message || "",
        diagnosticKnowledgeText: JSON.stringify(result.result?.knowledge_weights || {}, null, 2),
        diagnosticTopMatchesText: JSON.stringify(result.result?.top_matches || [], null, 2),
      });

      if (result.status === "completed") {
        wx.showToast({ title: "诊断完成", icon: "success" });
        return;
      }
      wx.showToast({ title: result.error_message || "诊断失败", icon: "none" });
    } catch (error) {
      console.error(error);
      const message = getErrorMessage(error, "诊断失败");
      this.setData({
        diagnosticStatus: "failed",
        diagnosticError: message,
      });
      wx.showToast({ title: message, icon: "none" });
    } finally {
      wx.hideLoading();
    }
  },

  handleRawTextInput(event) {
    this.setData({
      rawText: event.detail.value,
    });
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
