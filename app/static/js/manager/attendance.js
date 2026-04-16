API.attendance().then(data => {
  const body = document.getElementById('attendance-body')
  body.innerHTML = ''

  data.forEach(e => {
    body.innerHTML += `
      <tr>
        <td>${e.name}</td>
        <td>${e.check_in || '--'}</td>
        <td>${e.check_out || '--'}</td>
        <td>
          <span class="status ${e.status}">
            ${formatStatus(e.status)}
          </span>
        </td>
      </tr>
    `
  })
})

function formatStatus(status){
  switch(status){
    case "ON_TIME": return "🟢 Đúng giờ"
    case "LATE": return "🟡 Đi muộn"
    case "ABSENT": return "🔴 Vắng"
    case "LEAVE": return "🌴 Nghỉ phép"
    default: return status
  }
}

function sendReminder(){
  API.attendance().then(data=>{
    const ids = data.map(e => e.employee_id)
    API.reminder(ids).then(()=>alert("Đã gửi nhắc nhở"))
  })
}