export const isEmail = (email) => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
};

export const isPhoneVN = (phone) => {
  const regex = /^(0|\+84)[0-9]{9,10}$/;
  return regex.test(phone);
};

export const isEmpty = (value) => {
  return value === null || value === undefined || String(value).trim() === "";
};

export const minLength = (value, min) => {
  if (!value) return false;
  return String(value).length >= min;
};

export const maxLength = (value, max) => {
  if (!value) return true;
  return String(value).length <= max;
};

export const isDateValid = (dateStr) => {
  return !isNaN(new Date(dateStr).getTime());
};

export const validateRequiredFields = (obj, fields = []) => {
  const errors = {};

  fields.forEach((field) => {
    if (isEmpty(obj[field])) {
      errors[field] = `${field} is required`;
    }
  });

  return errors;
};