const { LOCAL_API_BASE_URL, buildApiUrl, getApiBaseUrl } = require("./config");

function sanitizeApiBaseUrl(url) {
  if (!url || typeof url !== "string") {
    return LOCAL_API_BASE_URL;
  }
  if (
    url.includes("localhost") ||
    url.includes("127.0.0.1") ||
    url.includes("yourdomain.com")
  ) {
    return LOCAL_API_BASE_URL;
  }
  return url;
}

function normalizeErrorPayload(res) {
  if (!res) return { detail: "请求失败" };
  if (res.statusCode === 401) {
    wx.removeStorageSync("access_token");
    wx.removeStorageSync("user_profile");
  }
  if (res.data && typeof res.data === "object") {
    return res.data;
  }
  if (typeof res.data === "string" && res.data.trim()) {
    return { detail: res.data.trim(), statusCode: res.statusCode };
  }
  return {
    detail: res.errMsg || `请求失败(${res.statusCode || "unknown"})`,
    statusCode: res.statusCode,
  };
}

function request({ url, method = "GET", data, token, timeout = 60000 }) {
  return new Promise((resolve, reject) => {
    const apiBaseUrl = sanitizeApiBaseUrl(getApiBaseUrl());
    const normalizedUrl = String(url || "").replace(apiBaseUrl, "").trim();
    const fullUrl = buildApiUrl(normalizedUrl);
    console.log("wx.request ->", fullUrl);

    wx.request({
      url: fullUrl,
      method,
      data,
      timeout,
      header: token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {},
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(normalizeErrorPayload(res));
      },
      fail(error) {
        reject(error);
      },
    });
  });
}

module.exports = {
  request,
};
