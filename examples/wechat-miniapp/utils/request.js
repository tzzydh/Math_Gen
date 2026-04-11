const { LOCAL_API_BASE_URL, getApiBaseUrl } = require("./config");

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

function request({ url, method = "GET", data, token, timeout = 60000 }) {
  return new Promise((resolve, reject) => {
    const apiBaseUrl = sanitizeApiBaseUrl(getApiBaseUrl());
    const fullUrl = `${apiBaseUrl}${url}`;
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
        reject(res.data || res);
      },
      fail: reject,
    });
  });
}

module.exports = {
  request,
};
