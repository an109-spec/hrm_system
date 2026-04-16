API.dashboard().then(data => {
  document.getElementById('total').innerText = data.total
  document.getElementById('working').innerText = data.working
  document.getElementById('on_leave').innerText = data.on_leave
  document.getElementById('late').innerText = data.late
  document.getElementById('absent').innerText = data.absent
  document.getElementById('pending').innerText = data.pending_leave
})