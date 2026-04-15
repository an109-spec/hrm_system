export const formatCurrency = (value) => {
  if (value === null || value === undefined) return "0";

  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(value);
};

export const formatNumber = (value) => {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat("vi-VN").format(value);
};

export const formatText = (text) => {
  if (!text) return "";
  return String(text).trim();
};

export const maskEmail = (email) => {
  if (!email || !email.includes("@")) return email;

  const [name, domain] = email.split("@");
  return `${name.slice(0, 2)}***@${domain}`;
};

export const capitalize = (str) => {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
};