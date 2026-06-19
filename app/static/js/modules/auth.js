/**
 * auth.js
 * Module xu ly toan bo logic Frontend cho cac trang xac thuc:
 *   - Login
 *   - Forgot Password
 *   - Verify OTP
 *   - Password Reset
 *
 * Phu thuoc: SweetAlert2 (Swal), Bootstrap 5
 * Path: app/static/js/modules/auth.js
 */

const Auth = (function () {

    // =========================================================
    // UTILITIES DUNG CHUNG
    // =========================================================

    /**
     * Hien thi trang thai loading cho nut bam.
     */
    function setLoading(btnId, spinnerId, textId, isLoading) {
        const btn = document.getElementById(btnId);
        const spinner = document.getElementById(spinnerId);
        const text = document.getElementById(textId);
        if (!btn) return;

        btn.disabled = isLoading;
        if (spinner) spinner.classList.toggle('d-none', !isLoading);
        if (text)    text.classList.toggle('d-none', isLoading);
    }

    /**
     * Xu ly phan hoi JSON tu server theo chuan SweetAlert2.
     * Neu co redirect_url, chuyen huong sau khi dong Swal.
     */
    function handleSwalResponse(data) {
        if (!data || !data.swal) return;

        const swalConfig = {
            icon:  data.swal.icon  || 'info',

            text:  data.swal.text  || '',
        };

        if (data.redirect_url) {
            swalConfig.timer = 1800;
            swalConfig.timerProgressBar = true;
            swalConfig.showConfirmButton = false;
        }

        Swal.fire(swalConfig).then(() => {
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            }
        });
    }

    /**
     * Danh dau loi tren input field.
     */
    function showFieldError(inputId, errorId, message) {
        const input = document.getElementById(inputId);
        const error = document.getElementById(errorId);
        if (input) input.classList.add('is-invalid');
        if (error) error.textContent = message;
    }

    function clearFieldErrors(form) {
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
    }

    /**
     * Toggle hien thi/an mat khau.
     */
    function setupPasswordToggle(btnId, inputId, iconId) {
        const btn   = document.getElementById(btnId);
        const input = document.getElementById(inputId);
        const icon  = document.getElementById(iconId);
        if (!btn || !input) return;

        btn.addEventListener('click', function () {
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            if (icon) {
                icon.className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
            }
        });
    }

    /**
     * Danh gia do manh mat khau va cap nhat UI.
     */
    function setupPasswordStrength(inputId, barId, textId, requirementsMap) {
        const input = document.getElementById(inputId);
        const bar   = document.getElementById(barId);
        const text  = document.getElementById(textId);
        if (!input || !bar) return;

        input.addEventListener('input', function () {
            const val = this.value;
            const strength = evaluatePasswordStrength(val);

            bar.className = 'password-strength-bar';
            if (val.length === 0) {
                bar.style.width = '0%';
                if (text) text.textContent = '';
            } else if (strength === 1) {
                bar.classList.add('strength-weak');
                if (text) { text.textContent = 'Yeu'; text.className = 'strength-text text-danger'; }
            } else if (strength === 2) {
                bar.classList.add('strength-medium');
                if (text) { text.textContent = 'Trung binh'; text.className = 'strength-text text-warning'; }
            } else {
                bar.classList.add('strength-strong');
                if (text) { text.textContent = 'Manh'; text.className = 'strength-text text-success'; }
            }

            // Cap nhat requirements list neu co
            if (requirementsMap) {
                Object.entries(requirementsMap).forEach(([reqId, testFn]) => {
                    const el = document.getElementById(reqId);
                    if (el) {
                        const met = testFn(val);
                        el.classList.toggle('met', met);
                        const icon = el.querySelector('i');
                        if (icon) icon.className = met ? 'fas fa-check-circle' : 'fas fa-circle';
                    }
                });
            }
        });
    }

    function evaluatePasswordStrength(password) {
        if (!password || password.length < 6) return 1;
        let score = 0;
        if (password.length >= 8)              score++;
        if (/[A-Z]/.test(password))            score++;
        if (/[0-9]/.test(password))            score++;
        if (/[^A-Za-z0-9]/.test(password))    score++;
        if (score <= 1) return 1;
        if (score <= 3) return 2;
        return 3;
    }

    /**
     * Dem nguoc (giay) -> cap nhat element va goi callback khi het gio.
     * Tra ve ham clear de stop timer.
     */
    function startCountdown(displayId, seconds, onExpire) {
        let remaining = seconds;
        const el = document.getElementById(displayId);

        function update() {
            if (!el) return;
            const m = String(Math.floor(remaining / 60)).padStart(2, '0');
            const s = String(remaining % 60).padStart(2, '0');
            el.textContent = m + ':' + s;
        }

        update();
        const interval = setInterval(function () {
            remaining--;
            update();
            if (remaining <= 0) {
                clearInterval(interval);
                if (onExpire) onExpire();
            }
        }, 1000);

        return function () { clearInterval(interval); };
    }

    // =========================================================
    // 1. TRANG DANG NHAP
    // =========================================================

    function initLogin() {
        const form = document.getElementById('loginForm');
        if (!form) return;

        setupPasswordToggle('togglePassword', 'password', 'toggleIcon');

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            clearFieldErrors(form);

            const identifier = document.getElementById('identifier').value.trim();
            const password   = document.getElementById('password').value;

            // Validate phia client
            if (!identifier) {
                showFieldError('identifier', 'identifierError', 'Vui long nhap Email hoac So dien thoai');
                return;
            }
            if (!password) {
                showFieldError('password', 'passwordError', 'Vui long nhap mat khau');
                return;
            }

            setLoading('loginBtn', 'loginBtnSpinner', 'loginBtnText', true);

            try {
                const resp = await fetch('/auth/login', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({ identifier, password }),
                });

                const data = await resp.json();

                if (!resp.ok) {
                    handleSwalResponse(data);
                    return;
                }

                handleSwalResponse(data);

            } catch (err) {
                Swal.fire({
                    icon:  'error',                    text:  'Khong the ket noi den may chu. Vui long thu lai.',
                });
            } finally {
                setLoading('loginBtn', 'loginBtnSpinner', 'loginBtnText', false);
            }
        });
    }

    // =========================================================
    // 2. TRANG QUEN MAT KHAU
    // =========================================================

    function initForgotPassword() {
        const form = document.getElementById('forgotPasswordForm');
        if (!form) return;

        let resendIntervalId = null;
        let resendSeconds    = 60;

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            clearFieldErrors(form);

            const identifier = document.getElementById('identifier').value.trim();

            if (!identifier) {
                showFieldError('identifier', 'identifierError', 'Vui long nhap Email hoac So dien thoai');
                return;
            }

            setLoading('sendBtn', 'sendBtnSpinner', 'sendBtnText', true);

            try {
                const resp = await fetch('/auth/forgot-password', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({ identifier }),
                });

                const data = await resp.json();

                if (!resp.ok) {
                    handleSwalResponse(data);
                    return;
                }

                // Luu identifier vao sessionStorage de dung o trang verify-otp
                sessionStorage.setItem('hrm_reset_identifier', identifier);
                if (data.otp_type) {
                    sessionStorage.setItem('hrm_otp_type', data.otp_type);
                }

                // Hien countdown resend
                const resendCountdownEl = document.getElementById('resendCountdown');
                if (resendCountdownEl) {
                    resendCountdownEl.classList.remove('d-none');
                }

                // Bat dau countdown 60s
                _startResendCountdown();

                // Hien Swal va redirect neu co
                if (data.redirect_url) {
                    Swal.fire({
                        icon:              data.swal.icon,
                        text:              data.swal.text,
                        timer:             2000,
                        timerProgressBar:  true,
                        showConfirmButton: false,
                    }).then(() => {
                        window.location.href = data.redirect_url;
                    });
                } else {
                    handleSwalResponse(data);
                }

            } catch (err) {
                Swal.fire({
                    icon:  'error',
                    text:  'Khong the ket noi den may chu. Vui long thu lai.',
                });
            } finally {
                setLoading('sendBtn', 'sendBtnSpinner', 'sendBtnText', false);
            }
        });

        function _startResendCountdown() {
            resendSeconds = 60;
            const display = document.getElementById('countdownTimer');
            const box     = document.getElementById('resendCountdown');
            if (box) box.classList.remove('d-none');

            if (resendIntervalId) clearInterval(resendIntervalId);
            resendIntervalId = setInterval(function () {
                resendSeconds--;
                if (display) display.textContent = resendSeconds;
                if (resendSeconds <= 0) {
                    clearInterval(resendIntervalId);
                    if (box) box.classList.add('d-none');
                    // Cho phep nop form lai
                    const sendBtn = document.getElementById('sendBtn');
                    if (sendBtn) sendBtn.disabled = false;
                }
            }, 1000);
        }
    }

    // =========================================================
    // 3. TRANG XAC MINH OTP + DOI MAT KHAU (verify_otp.html)
    // =========================================================

    function initVerifyOtp() {
        const form = document.getElementById('verifyOtpForm');
        if (!form) return;

        // Lay identifier tu sessionStorage (da luu tu buoc forgot-password)
        const savedIdentifier = sessionStorage.getItem('hrm_reset_identifier') || '';
        const savedOtpType    = sessionStorage.getItem('hrm_otp_type') || 'email';
        const identifierInput = document.getElementById('identifier');
        const otpTypeInput    = document.getElementById('otp_type');

        if (identifierInput) identifierInput.value = savedIdentifier;
        if (otpTypeInput)    otpTypeInput.value    = savedOtpType;

        // Neu khong co identifier, redirect ve forgot-password
        if (!savedIdentifier) {
            Swal.fire({
                icon:  'warning',
                text:  'Vui long thuc hien lai yeu cau doi mat khau.',
            }).then(() => {
                window.location.href = '/auth/forgot-password';
            });
            return;
        }

        // Dem nguoc 5 phut
        const clearTimer = startCountdown('otpTimerDisplay', 300, function () {
            const timerBox = document.getElementById('otpTimerBox');
            if (timerBox) {
                timerBox.classList.add('expired');
                timerBox.querySelector('#otpTimerDisplay').textContent = 'Het han';
            }
            const verifyBtn = document.getElementById('verifyBtn');
            if (verifyBtn) verifyBtn.disabled = true;

            Swal.fire({
                icon:  'warning',
                title: 'het han',
                text:  'Vui long yeu cau ma OTP moi.',
                confirmButtonText: 'Yeu cau ma moi',
            }).then(() => {
                window.location.href = '/auth/forgot-password';
            });
        });

        // Toggle mat khau
        setupPasswordToggle('toggleNewPwd',     'new_password',     'toggleNewPwdIcon');
        setupPasswordToggle('toggleConfirmPwd',  'confirm_password', 'toggleConfirmPwdIcon');

        // Do manh mat khau
        setupPasswordStrength('new_password', 'pwStrengthBar', 'pwStrengthText', {
            'req-length': function (v) { return v.length >= 8; },
            'req-upper':  function (v) { return /[A-Z]/.test(v); },
            'req-number': function (v) { return /[0-9]/.test(v); },
        });

        // Chi cho phep nhap so vao OTP
        const otpInput = document.getElementById('otp_code');
        if (otpInput) {
            otpInput.addEventListener('input', function () {
                this.value = this.value.replace(/\D/g, '').slice(0, 6);
            });
        }

        // Resend OTP countdown (60s)
        let resendSeconds = 60;
        const resendBtn   = document.getElementById('resendOtpBtn');
        const resendDisp  = document.getElementById('resendCountdown');

        const resendInterval = setInterval(function () {
            resendSeconds--;
            if (resendDisp) resendDisp.textContent = resendSeconds;
            if (resendSeconds <= 0) {
                clearInterval(resendInterval);
                if (resendBtn) {
                    resendBtn.disabled = false;
                    resendBtn.innerHTML = '<i class="fas fa-redo me-1"></i>Gui lai ma OTP';
                }
            }
        }, 1000);

        if (resendBtn) {
            resendBtn.addEventListener('click', async function () {
                if (!savedIdentifier) return;

                resendBtn.disabled = true;
                try {
                    const resp = await fetch('/auth/forgot-password', {
                        method:  'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body:    JSON.stringify({ identifier: savedIdentifier }),
                    });
                    const data = await resp.json();
                    handleSwalResponse(data);

                    if (resp.ok) {
                        // Reset countdown 60s
                        resendSeconds = 60;
                        if (resendDisp) resendDisp.textContent = resendSeconds;
                        resendBtn.innerHTML = '<i class="fas fa-redo me-1"></i>Gui lai ma OTP (<span id="resendCountdown">60</span>s)';
                        resendBtn.disabled = true;
                    } else {
                        resendBtn.disabled = false;
                    }
                } catch (_) {
                    resendBtn.disabled = false;
                }
            });
        }

        // Submit form
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            clearFieldErrors(form);

            const otp_code        = document.getElementById('otp_code').value.trim();
            const new_password    = document.getElementById('new_password').value;
            const confirm_password = document.getElementById('confirm_password').value;
            const identifier_val  = document.getElementById('identifier').value.trim();
            const otp_type_val    = document.getElementById('otp_type').value;

            // Validate
            let hasError = false;

            if (!otp_code || otp_code.length < 4) {
                showFieldError('otp_code', 'otpError', 'Vui long nhap ma OTP hop le');
                hasError = true;
            }
            if (!new_password || new_password.length < 8) {
                showFieldError('new_password', 'newPasswordError', 'Mat khau phai co toi thieu 8 ky tu');
                hasError = true;
            }
            if (new_password !== confirm_password) {
                showFieldError('confirm_password', 'confirmPasswordError', 'Mat khau xac nhan khong khop');
                hasError = true;
            }
            if (hasError) return;

            setLoading('verifyBtn', 'verifyBtnSpinner', 'verifyBtnText', true);

            try {
                const resp = await fetch('/auth/verify-otp', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({
                        identifier:   identifier_val,
                        otp_code:     otp_code,
                        new_password: new_password,
                        otp_type:     otp_type_val,
                    }),
                });

                const data = await resp.json();

                if (resp.ok) {
                    clearTimer();
                    sessionStorage.removeItem('hrm_reset_identifier');
                    sessionStorage.removeItem('hrm_otp_type');
                }

                handleSwalResponse(data);

            } catch (err) {
                Swal.fire({
                    icon:  'error',
                    text:  'Khong the ket noi den may chu. Vui long thu lai.',
                });
            } finally {
                setLoading('verifyBtn', 'verifyBtnSpinner', 'verifyBtnText', false);
            }
        });
    }

    // =========================================================
    // 4. TRANG DAT LAI MAT KHAU (password_reset.html)
    //    Dung khi can truyen san identifier + otp_code tu URL params
    // =========================================================

    function initPasswordReset() {
        const form = document.getElementById('resetPasswordForm');
        if (!form) return;

        // Doc params tu URL hoac sessionStorage
        const params     = new URLSearchParams(window.location.search);
        const identifier = params.get('identifier') || sessionStorage.getItem('hrm_reset_identifier') || '';
        const otp_code   = params.get('otp_code')   || sessionStorage.getItem('hrm_otp_code') || '';
        const otp_type   = params.get('otp_type')   || sessionStorage.getItem('hrm_otp_type') || 'email';

        const identifierInput = document.getElementById('identifier');
        const otpCodeInput    = document.getElementById('otp_code');
        const otpTypeInput    = document.getElementById('otp_type');

        if (identifierInput) identifierInput.value = identifier;
        if (otpCodeInput)    otpCodeInput.value    = otp_code;
        if (otpTypeInput)    otpTypeInput.value    = otp_type;

        // Toggle mat khau
        setupPasswordToggle('toggleNewPwd',     'new_password',     'toggleNewPwdIcon');
        setupPasswordToggle('toggleConfirmPwd',  'confirm_password', 'toggleConfirmPwdIcon');

        // Do manh mat khau voi requirements
        setupPasswordStrength('new_password', 'pwStrengthBar', 'pwStrengthText', {
            'req-length': function (v) { return v.length >= 8; },
            'req-upper':  function (v) { return /[A-Z]/.test(v); },
            'req-number': function (v) { return /[0-9]/.test(v); },
        });

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            clearFieldErrors(form);

            const new_password    = document.getElementById('new_password').value;
            const confirm_password = document.getElementById('confirm_password').value;
            const identifier_val  = document.getElementById('identifier').value.trim();
            const otp_code_val    = document.getElementById('otp_code').value.trim();
            const otp_type_val    = document.getElementById('otp_type').value;

            let hasError = false;

            if (!new_password || new_password.length < 8) {
                showFieldError('new_password', 'newPasswordError', 'Mat khau phai co toi thieu 8 ky tu');
                hasError = true;
            }
            if (new_password !== confirm_password) {
                showFieldError('confirm_password', 'confirmPasswordError', 'Mat khau xac nhan khong khop');
                hasError = true;
            }
            if (!identifier_val) {
                Swal.fire({
                    icon:  'error',

                    text:  'Khong xac dinh duoc tai khoan. Vui long thu lai tu dau.',
                });
                return;
            }
            if (hasError) return;

            setLoading('resetBtn', 'resetBtnSpinner', 'resetBtnText', true);

            try {
                const resp = await fetch('/auth/reset-password', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({
                        identifier:       identifier_val,
                        otp_code:         otp_code_val,
                        new_password:     new_password,
                        confirm_password: confirm_password,
                        otp_type:         otp_type_val,
                    }),
                });

                const data = await resp.json();

                if (resp.ok) {
                    sessionStorage.removeItem('hrm_reset_identifier');
                    sessionStorage.removeItem('hrm_otp_code');
                    sessionStorage.removeItem('hrm_otp_type');
                }

                handleSwalResponse(data);

            } catch (err) {
                Swal.fire({
                    icon:  'error',
                    text:  'Khong the ket noi den may chu. Vui long thu lai.',
                });
            } finally {
                setLoading('resetBtn', 'resetBtnSpinner', 'resetBtnText', false);
            }
        });
    }

    // =========================================================
    // PUBLIC API
    // =========================================================

    return {
        initLogin,
        initForgotPassword,
        initVerifyOtp,
        initPasswordReset,
    };

})();
