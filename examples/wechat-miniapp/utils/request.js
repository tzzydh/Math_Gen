const { API_BASE_URL } = require("./config");

function request({ url, method = "GET", data, token, timeout = 60000 }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${url}`,
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
