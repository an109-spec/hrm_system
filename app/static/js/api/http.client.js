const API_BASE = "/api";

/**
 * Lấy token từ Cookie hoặc LocalStorage
 */
function getToken() {
  // Ưu tiên 1: Nếu bạn lưu ở localStorage (dành cho các logic JS thuần)
  const token = localStorage.getItem("access_token");
  if (token) return token;

  // Ưu tiên 2: Nếu không có trong localStorage, trình duyệt sẽ tự gửi Cookie
  // (Bạn không cần code thêm gì vì fetch() sẽ tự đính kèm cookie nếu cùng domain)
  return null;
}

async function request(endpoint, options = {}) {
  const token = getToken();

  // Cấu hình mặc định cho fetch
  const defaultOptions = {
    headers: {
      "Content-Type": "application/json",
      // Nếu có token trong localStorage thì đính kèm vào Header
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    },
    // Quan trọng: credentials: 'include' giúp fetch gửi kèm Cookie (access_token_cookie)
    credentials: 'include', 
    ...options
  };

  const res = await fetch(API_BASE + endpoint, defaultOptions);

  if (!res.ok) {
    // Nếu bị 401 (Unauthorized), có thể Token hết hạn -> đẩy về login
    if (res.status === 401) {
      window.location.href = "/auth/login";
    }
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "API Error");
  }

  return res.json();
}

export default request;