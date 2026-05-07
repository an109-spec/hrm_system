// app/static/js/api/http.client.js

// Flask blueprint không dùng prefix /api — gọi thẳng path
const API_BASE = "";

function getToken() {
  return localStorage.getItem("access_token") || null;
}

async function request(endpoint, options = {}) {
  const token = getToken();

  const defaultOptions = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    credentials: "include",
    ...options,
  };

  let res;
  try {
    res = await fetch(API_BASE + endpoint, defaultOptions);
  } catch (networkErr) {
    throw new Error("Không thể kết nối server. Kiểm tra mạng và thử lại.");
  }

  if (res.status === 401) {
    window.location.href = "/auth/login";
    throw new Error("Phiên đăng nhập hết hạn");
  }

  // Đọc body một lần
  let data;
  try {
    data = await res.json();
  } catch (_) {
    throw new Error(`Lỗi server (${res.status})`);
  }

  if (!res.ok) {
    // Ưu tiên message từ server, rồi mới dùng status text
    const msg = data?.message || data?.error || `Lỗi ${res.status}`;
    throw new Error(msg);
  }

  return data;
}

export default request;
