/**
 * Обёртка fetch для JSON API: подставляет X-API-Key из sessionStorage,
 * при 401 один раз запрашивает ключ через prompt (внутренние/демо-сценарии).
 */
(function () {
  var STORAGE_KEY = "bizsf_api_key";

  function getKey() {
    return sessionStorage.getItem(STORAGE_KEY) || "";
  }

  window.bizsfSetApiKey = function (k) {
    if (k && String(k).trim()) {
      sessionStorage.setItem(STORAGE_KEY, String(k).trim());
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  };

  window.bizsfApiFetch = function (url, options) {
    options = options || {};
    var headers = Object.assign({}, options.headers || {});
    var k = getKey();
    if (k) {
      headers["X-API-Key"] = k;
    }
    options.headers = headers;
    return fetch(url, options).then(function (res) {
      if (res.status !== 401) {
        return res;
      }
      var msg =
        "Сервер требует API-ключ (переменная API_KEY). Введите ключ — он сохранится в sessionStorage этой вкладки:";
      var input = typeof prompt === "function" ? prompt(msg) : null;
      if (input && String(input).trim()) {
        window.bizsfSetApiKey(input);
        headers["X-API-Key"] = String(input).trim();
        options.headers = headers;
        return fetch(url, options);
      }
      return res;
    });
  };
})();
