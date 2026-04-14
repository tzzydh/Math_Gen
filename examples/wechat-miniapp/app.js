const {
  clearInvalidOverride,
  getApiBaseUrl,
  getConfiguredProdApiBaseUrl,
  isDevtools,
} = require("./utils/config");

App({
  onLaunch() {
    clearInvalidOverride();
    this.globalData = this.globalData || {};
    this.globalData.apiBaseUrl = getApiBaseUrl();
    this.globalData.runtimeMode = isDevtools() ? "development" : "production";
    this.globalData.prodApiBaseUrl = getConfiguredProdApiBaseUrl();
    console.log("miniapp runtime mode:", this.globalData.runtimeMode);
    console.log("miniapp api base:", this.globalData.apiBaseUrl);
    if (
      this.globalData.runtimeMode === "production" &&
      !this.globalData.prodApiBaseUrl
    ) {
      console.warn(
        "production api domain is not configured; falling back to local API base URL"
      );
    }
  },
});
