const { clearInvalidOverride, getApiBaseUrl } = require("./utils/config");

App({
  onLaunch() {
    clearInvalidOverride();
    this.globalData = this.globalData || {};
    this.globalData.apiBaseUrl = getApiBaseUrl();
    console.log("miniapp api base:", this.globalData.apiBaseUrl);
  },
});
