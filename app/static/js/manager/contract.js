API.contracts().then(data => {
  const list = document.getElementById('contract-list')
  list.innerHTML = ''

  data.forEach(c => {
    list.innerHTML += `<li>📄 ${c}</li>`
  })
})

function openModal(){
  document.getElementById('contract-modal').style.display = 'block'
}

function closeModal(){
  document.getElementById('contract-modal').style.display = 'none'
}

function renew(){
  const data = {
    employee_id: document.getElementById('emp_id').value,
    contract_code: document.getElementById('code').value,
    basic_salary: parseFloat(document.getElementById('salary').value),
    start_date: document.getElementById('start').value,
    end_date: document.getElementById('end').value || null
  }

  API.renew(data).then(()=>{
    alert("Gia hạn thành công")
    closeModal()
  })
}