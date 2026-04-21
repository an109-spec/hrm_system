// TAB SWITCH
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
  });
});

let selectedFile = null;

const input = document.getElementById("avatarInput");
const uploadBtn = document.getElementById("uploadAvatarBtn");

// PREVIEW ẢNH
if (input) {
  input.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;

    selectedFile = file;

    const reader = new FileReader();

    reader.onload = function (ev) {
      let avatar = document.querySelector(".profile-avatar");

      // nếu chưa có img thì tạo
      if (!avatar) {
        const wrapper = document.querySelector(".avatar-wrapper");
        wrapper.innerHTML = `<img class="profile-avatar">`;
        avatar = document.querySelector(".profile-avatar");
      }

      avatar.src = ev.target.result;
    };

    reader.readAsDataURL(file);
  });
}

// UPLOAD ẢNH (QUAN TRỌNG)
if (uploadBtn) {
  uploadBtn.addEventListener("click", async () => {
    if (!selectedFile) {
      alert("Chưa chọn ảnh");
      return;
    }

    const formData = new FormData();
    formData.append("avatar", selectedFile);

    try {
      uploadBtn.innerText = "Đang upload...";
      uploadBtn.disabled = true;

      fetch("/employee/upload-avatar", {
        method: "POST",
        body: formData
      });

      if (res.ok) {
        alert("Cập nhật thành công");
        location.reload();
      } else {
        alert("Upload thất bại");
      }
    } catch (err) {
      alert("Lỗi server");
    } finally {
      uploadBtn.innerText = "Cập nhật ảnh";
      uploadBtn.disabled = false;
    }
  });
}

// TOAST SIMPLE
function showToast(msg, type="success") {
  const toast = document.createElement("div");
  toast.className = "toast " + type;
  toast.innerText = msg;

  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 3000);
}