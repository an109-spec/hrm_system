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

      const res = await fetch("/employee/upload-avatar", {
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
// --- XỬ LÝ CHỈNH SỬA VÀ ĐỊA CHỈ ---
const profileForm = document.getElementById('profileForm');
const editBtn = document.getElementById('editBtn');
const cancelBtn = document.getElementById('cancelBtn');
const saveCancelActions = document.getElementById('saveCancelActions');
const inputs = profileForm.querySelectorAll('input, select');

// Hàm bật/tắt chế độ chỉnh sửa
function toggleEditMode(isEditing) {
    inputs.forEach(input => {
        if (!input.readOnly || input.tagName === 'SELECT' || input.id === 'detailAddress') {
            if (input.getAttribute('name') !== 'email') { // Không cho sửa email
                if (input.tagName === 'SELECT') input.disabled = !isEditing;
                else input.readOnly = !isEditing;
                input.classList.toggle('readonly-input', !isEditing);
            }
        }
    });
    editBtn.style.display = isEditing ? 'none' : 'block';
    saveCancelActions.style.display = isEditing ? 'flex' : 'none';
}

editBtn.addEventListener('click', () => toggleEditMode(true));
cancelBtn.addEventListener('click', () => {
    toggleEditMode(false);
    location.reload(); // Hoàn tác các thay đổi bằng cách load lại
});

const host = "https://provinces.open-api.vn/api/";
const addressData = document.getElementById('addressData');

// Hàm khởi tạo địa chỉ cũ khi load trang
async function initAddress() {
    const pCode = addressData.dataset.province;
    const dCode = addressData.dataset.district;
    const wCode = addressData.dataset.ward;

    // 1. Load tỉnh
    const provinces = await fetch(host + "?depth=1").then(res => res.json());
    renderData(provinces, "province");
    
    if (pCode) {
        document.getElementById('province').value = pCode;
        // 2. Load huyện
        const districts = await fetch(host + "p/" + pCode + "?depth=2").then(res => res.json());
        renderData(districts.districts, "district");
        
        if (dCode) {
            document.getElementById('district').value = dCode;
            // 3. Load xã
            const wards = await fetch(host + "d/" + dCode + "?depth=2").then(res => res.json());
            renderData(wards.wards, "ward");
            if (wCode) document.getElementById('ward').value = wCode;
        }
    }
}

var renderData = (array, selectId) => {
    let row = '<option value="">Chọn</option>';
    array.forEach(element => {
        row += `<option value="${element.code}">${element.name}</option>`;
    });
    document.querySelector("#" + selectId).innerHTML = row;
}

// Gọi hàm init khi load trang
initAddress();

// Giữ nguyên các EventListener change của bạn nhưng chỉnh lại tên selectId
document.querySelector("#province").addEventListener("change", async (e) => {
    if (!e.target.value) return;
    const data = await fetch(host + "p/" + e.target.value + "?depth=2").then(res => res.json());
    renderData(data.districts, "district");
    document.querySelector("#ward").innerHTML = '<option value="">Chọn</option>';
});

document.querySelector("#district").addEventListener("change", async (e) => {
    if (!e.target.value) return;
    const data = await fetch(host + "d/" + e.target.value + "?depth=2").then(res => res.json());
    renderData(data.wards, "ward");
});

profileForm.addEventListener('submit', async (e) => {
    e.preventDefault(); // Chặn load trang mặc định

// Mở khóa tạm thời để lấy được dữ liệu từ các ô disabled
    inputs.forEach(i => i.disabled = false); 
    
    const formData = new FormData(profileForm);
    const data = Object.fromEntries(formData.entries());

    // Khóa lại ngay sau khi lấy xong dữ liệu
    inputs.forEach(i => {
        if (i.tagName === 'SELECT') i.disabled = true;
    });

    try {
        const response = await fetch("/employee/update-profile", { // Thay đổi URL này đúng với route của bạn
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert("Cập nhật thông tin thành công!");
            location.reload(); // Load lại để hiển thị dữ liệu mới từ Database
        } else {
            const err = await response.json();
            alert("Lỗi: " + (err.error || "Không thể lưu"));
        }
    } catch (error) {
        console.error(error);
        alert("Lỗi kết nối server");
    }
});

profileForm.addEventListener('submit', async (e) => {
    const submitter = e.submitter;
    
    if (submitter && submitter.value === 'change_password') {
        return; 
    }

    e.preventDefault(); 

    inputs.forEach(i => i.disabled = false); 
    
    const formData = new FormData(profileForm);
    const data = Object.fromEntries(formData.entries());

    inputs.forEach(i => {
        if (i.tagName === 'SELECT') i.disabled = true;
    });

    try {
        const response = await fetch("/employee/update-profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert("Cập nhật thông tin thành công!");
            location.reload(); 
        } else {
            const err = await response.json();
            alert("Lỗi: " + (err.error || "Không thể lưu"));
        }
    } catch (error) {
        console.error(error);
        alert("Lỗi kết nối server");
    }
});