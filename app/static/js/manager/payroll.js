function loadSalary(){
  const m = document.getElementById('month').value
  const y = document.getElementById('year').value

  API.salary(m,y).then(data=>{
    const list = document.getElementById('salary-list')
    list.innerHTML = ''

    data.forEach(id=>{
      list.innerHTML += `<li>Salary ID: ${id}</li>`
    })
  })
}