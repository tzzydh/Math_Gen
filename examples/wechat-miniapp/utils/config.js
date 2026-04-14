const LOCAL_API_BASE_URL = "http://192.168.31.159:8000/api/v1";
const PROD_API_BASE_URL = "";
const PROD_API_BASE_URL_PLACEHOLDER = "https://api.yourdomain.com/api/v1";

function isInvalidUrl(url) {
  if (!url || typeof url !== "string") {
    return true;
  }
  if (!/^https?:\/\//.test(url)) {
    return true;
  }
  return (
    url.includes("localhost") ||
    url.includes("127.0.0.1") ||
    url.includes("yourdomain.com")
  );
}

function normalizeApiBaseUrl(url) {
  return String(url || "")
    .trim()
    .replace(/\/+$/, "");
}

function readOverride() {
  try {
    return wx.getStorageSync("api_base_url_override");
  } catch (error) {
    console.log("read api_base_url_override failed", error);
    return "";
  }
}

function readProdOverride() {
  try {
    return wx.getStorageSync("api_base_url_prod_override");
  } catch (error) {
    console.log("read api_base_url_prod_override failed", error);
    return "";
  }
}

function clearInvalidOverride() {
  try {
    const override = readOverride();
    if (isInvalidUrl(override)) {
      wx.removeStorageSync("api_base_url_override");
    }
    const prodOverride = readProdOverride();
    if (isInvalidUrl(prodOverride)) {
      wx.removeStorageSync("api_base_url_prod_override");
    }
  } catch (error) {
    console.log("clear invalid override failed", error);
  }
}

function isDevtools() {
  try {
    const systemInfo = wx.getSystemInfoSync();
    return systemInfo && systemInfo.platform === "devtools";
  } catch (error) {
    console.log("getSystemInfoSync failed", error);
    return false;
  }
}

function getConfiguredProdApiBaseUrl() {
  const prodOverride = readProdOverride();
  if (!isInvalidUrl(prodOverride)) {
    return normalizeApiBaseUrl(prodOverride);
  }
  if (!isInvalidUrl(PROD_API_BASE_URL)) {
    return normalizeApiBaseUrl(PROD_API_BASE_URL);
  }
  return "";
}

function getPreferredApiBaseUrl() {
  if (isDevtools()) {
    return normalizeApiBaseUrl(LOCAL_API_BASE_URL);
  }
  const prodApiBaseUrl = getConfiguredProdApiBaseUrl();
  if (prodApiBaseUrl) {
    return prodApiBaseUrl;
  }
  return normalizeApiBaseUrl(LOCAL_API_BASE_URL);
}

function getApiBaseUrl() {
  const override = readOverride();
  if (!isInvalidUrl(override)) {
    return normalizeApiBaseUrl(override);
  }
  return getPreferredApiBaseUrl();
}

function buildApiUrl(path = "") {
  const baseUrl = getApiBaseUrl();
  const normalizedPath = String(path || "")
    .trim()
    .replace(/^\/+/, "");
  return normalizedPath ? `${baseUrl}/${normalizedPath}` : baseUrl;
}

module.exports = {
  LOCAL_API_BASE_URL,
  PROD_API_BASE_URL,
  PROD_API_BASE_URL_PLACEHOLDER,
  buildApiUrl,
  clearInvalidOverride,
  getConfiguredProdApiBaseUrl,
  getApiBaseUrl,
  getPreferredApiBaseUrl,
  isDevtools,
  normalizeApiBaseUrl,
};
