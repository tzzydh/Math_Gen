# WeChat Mini Program Example

This folder contains a minimal native WeChat Mini Program example that demonstrates:

1. Login with `wx.login`
2. Exchange the code for your backend JWT
3. Request an OSS upload policy
4. Upload an image directly to OSS
5. Confirm the uploaded asset with the backend

Local debug tips:

1. Open project details and turn on `不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书`
2. If devtools still reports old domains, clear cache and recompile
3. Default local API base is `http://192.168.31.159:8000/api/v1`
4. Real device / preview still requires a legal HTTPS domain configured in the WeChat admin console
