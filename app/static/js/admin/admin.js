async function api(url, options={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...options});if(!r.ok){const e=await r.json().catch(()=>({error:'error'}));throw new Error(e.error||'Request failed')}return r.headers.get('content-type')?.includes('application/json')?r.json():r.text()}
const now=new Date();
function setDefaults(){const m=document.getElementById('month');const y=document.getElementById('year');if(m&&!m.value)m.value=now.getMonth()+1;if(y&&!y.value)y.value=now.getFullYear();}
async function loadDepartmentsSelect(){const el=document.getElementById('department');if(!el)return;const rows=await api('/api/departments');el.innerHTML='<option value="">Tất cả phòng ban</option>'+rows.map(d=>`<option value="${d.id}">${d.name}</option>`).join('')}

async function loadDashboard(){setDefaults();const m=month.value,y=year.value,d=department?.value||'';const data=await api(`/api/dashboard/overview?month=${m}&year=${y}&department_id=${d}`);const employeeStats=document.getElementById('employeeStats');const attendanceStats=document.getElementById('attendanceStats');const salaryStats=document.getElementById('salaryStats');const activities=document.getElementById('activities');if(!employeeStats||!attendanceStats||!salaryStats||!activities)return;
employeeStats.innerHTML=`
  <p><strong>👥 Nhân sự</strong></p>
  <p>Tổng nhân sự: ${data.employee.total ?? 0}</p>
  <p>Nhân viên mới: ${data.employee.new ?? 0}</p>
  <p>Nghỉ việc: ${data.employee.resigned ?? 0}</p>
  <p>Sắp hết hạn hợp đồng: ${data.employee.expiring_contract ?? 0}</p>`;
attendanceStats.innerHTML=`
  <p>Tỉ lệ chuyên cần toàn công ty: ${data.attendance.attendance_rate ?? 0}%</p>
  <p>Phòng ban nào có tỉ lệ đi muộn cao nhất: ${data.attendance.hotspot_department?.department_id ?? 'N/A'}</p>
  <p>Tổng lượt đi muộn: ${data.attendance.late_count ?? 0}</p>
  <p>Tổng lượt vắng mặt: ${data.attendance.absent_count ?? 0}</p>`;
salaryStats.innerHTML=`
  <p>Tổng quỹ lương tháng hiện tại: ${Number(data.salary.total_salary ?? 0).toLocaleString('vi-VN')} VND</p>
  <p>Số lượng bản ghi lương: ${data.salary.salary_records ?? 0}</p>
  <p>Thuế & Bảo hiểm: Theo dữ liệu bảng lương hiện tại</p>`;
activities.innerHTML=data.activities.map(a=>`<li>[${a.time||'--'}] ${a.action}</li>`).join('') || '<li>Chưa có dữ liệu.</li>'}

async function loadEmployees(){const res=await api('/api/departments');const rows=await api('/api/dashboard/employees');const tr=document.getElementById('employeeRows');const emps=await fetch('/api/departments').then(()=>[]).catch(()=>[]); // placeholder
tr.innerHTML='<tr><td colspan="6">Dùng API /api/admin/users/{id}/lock và /role để thao tác từ màn này.</td></tr>'}

async function loadDepartments(){const rows=await api('/api/departments');departmentRows.innerHTML=rows.map(r=>`<tr><td>${r.department_code}</td><td>${r.name}</td><td>${r.manager_name||''}</td><td>${r.employee_count}</td><td><span class="badge ${r.status?'b-success':'b-danger'}">${r.status?'active':'inactive'}</span></td><td><button onclick="toggleDepartment(${r.id},${r.status})">${r.status?'Disable':'Enable'}</button></td></tr>`).join('')}
async function toggleDepartment(id,status){if(status){await api(`/api/departments/${id}`,{method:'DELETE'})}else{await api(`/api/departments/${id}`,{method:'PATCH',body:JSON.stringify({status:true})})}loadDepartments()}
async function createDepartmentPrompt(){const {value:name}=await Swal.fire({title:'Tên phòng ban',input:'text',showCancelButton:true});if(!name)return;await api('/api/departments',{method:'POST',body:JSON.stringify({name})});await Swal.fire({icon:'success',title:'Đã tạo phòng ban'});loadDepartments();}

async function loadPositions(){const rows=await api('/api/positions');positionRows.innerHTML=rows.map(r=>`<tr><td>${r.id}</td><td>${r.job_title}</td><td>${r.salary_range}</td><td>${r.employee_count}</td><td>${r.status}</td><td><button onclick="togglePosition(${r.id},'${r.status}')">${r.status==='inactive'?'Enable':'Disable'}</button></td></tr>`).join('')}
async function togglePosition(id,status){await api(`/api/positions/${id}/status`,{method:'PATCH',body:JSON.stringify({status:status==='inactive'?'active':'inactive'})});loadPositions()}
async function createPositionPrompt(){const {value:job_title}=await Swal.fire({title:'Tên chức danh',input:'text',showCancelButton:true});if(!job_title)return;await api('/api/positions',{method:'POST',body:JSON.stringify({job_title,min_salary:0,max_salary:0,status:'active'})});await Swal.fire({icon:'success',title:'Đã tạo chức danh'});loadPositions();}

async function loadAttendanceSummary(){setDefaults();const m=month.value,y=year.value;const rows=await api(`/api/admin/attendance/summary?month=${m}&year=${y}`);attendanceRows.innerHTML=rows.map(r=>`<tr><td>${r.department_name}</td><td>${r.employee_count}</td><td>${r.total_work}</td><td>${r.late_count}</td><td>${r.absent_count}</td></tr>`).join('');const logs=await api(`/api/admin/attendance/audit-log?month=${m}&year=${y}`);attendanceAudit.innerHTML=logs.map(l=>`<li>${l.time||''} | ${l.action} | ${l.description||''}</li>`).join('')}
async function lockMonth(){setDefaults();await api('/api/admin/attendance/lock-month',{method:'POST',body:JSON.stringify({month:+month.value,year:+year.value})});loadAttendanceSummary()}
async function reopenMonth(){setDefaults();const {value:reason}=await Swal.fire({title:'Nhập lý do mở lại công',input:'text',showCancelButton:true});if(reason===undefined)return;await api('/api/admin/attendance/reopen-month',{method:'POST',body:JSON.stringify({month:+month.value,year:+year.value,reason:reason||''})});await Swal.fire({icon:'success',title:'Đã mở lại bảng công'});loadAttendanceSummary()}

async function loadSalaryAggregate(){setDefaults();const g=document.getElementById('groupBy').value;const m=month.value,y=year.value;const res=await api(`/api/admin/salaries/aggregate?month=${m}&year=${y}&group_by=${g}`);salaryStatus.textContent=`Trạng thái: ${res.status}`;salaryRows.innerHTML=res.data.map(r=>`<tr><td>${r.group_name}</td><td>${r.employee_count}</td><td>${r.total_salary}</td><td>${r.avg_salary}</td></tr>`).join('');const logs=await api('/api/admin/salaries/audit');salaryAudit.innerHTML=logs.map(l=>`<li>${l.time||''} | ${l.action} | ${l.description||''}</li>`).join('')}
async function lockSalary(){setDefaults();await api('/api/admin/salaries/lock',{method:'POST',body:JSON.stringify({month:+month.value,year:+year.value})});loadSalaryAggregate()}
async function unlockSalary(){setDefaults();await api('/api/admin/salaries/unlock',{method:'POST',body:JSON.stringify({month:+month.value,year:+year.value})});loadSalaryAggregate()}

document.addEventListener('DOMContentLoaded',async()=>{setDefaults();await loadDepartmentsSelect();if(window.ADMIN_PAGE==='dashboard'){await loadDashboard();}
if(window.ADMIN_PAGE==='employees'){await loadEmployees();}
if(window.ADMIN_PAGE==='departments'){await loadDepartments();}
if(window.ADMIN_PAGE==='positions'){await loadPositions();}
if(window.ADMIN_PAGE==='attendance'){await loadAttendanceSummary();}
if(window.ADMIN_PAGE==='salary'){await loadSalaryAggregate();}})