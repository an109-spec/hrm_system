function loadLeaves(){
  const status = document.getElementById('statusFilter').value

  API.leaves(status).then(data=>{
    const body = document.getElementById('leave-body')
    body.innerHTML = ''

    data.forEach(id=>{
      body.innerHTML += `
        <tr>
          <td>${id}</td>
          <td>
            <button onclick="approve(${id})">✔️</button>
            <button onclick="reject(${id})">❌</button>
          </td>
        </tr>
      `
    })
  })
}

function approve(id){
  API.approve(id).then(()=>loadLeaves())
}

function reject(id){
  API.reject(id).then(()=>loadLeaves())
}

loadLeaves()