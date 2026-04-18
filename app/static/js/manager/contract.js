let expiringContracts = []
let selectedContract = null

function openModal(contract) {
  selectedContract = contract
  document.getElementById('emp_id').value = contract.employee_id
  document.getElementById('old_code').value = contract.contract_code
  document.getElementById('code').value = ''
  document.getElementById('salary').value = contract.basic_salary
  document.getElementById('start').value = contract.end_date
  document.getElementById('end').value = ''
  document.getElementById('contract-modal').hidden = false
}

function closeModal() {
  selectedContract = null
  document.getElementById('contract-modal').hidden = true
}

function renderContracts() {
  const list = document.getElementById('contract-list')
  list.innerHTML = expiringContracts
    .map(
      (item) => `<li>📄 ${item.employee_name} - ${item.contract_code} (còn ${item.days_left} ngày) <button data-id="${item.id}">📑 Gia hạn</button></li>`
    )
    .join('')

  list.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const contract = expiringContracts.find((c) => c.id === Number(btn.dataset.id))
      openModal(contract)
    })
  })

}

async function loadContracts() {
  try {
    expiringContracts = await ManagerAPI.contractsExpiring()
    renderContracts()
  } catch (err) {
    const box = document.getElementById('contract-error')
    box.hidden = false
    box.textContent = err.message
  }
}

async function submitRenew() {
  if (!selectedContract) return

  const payload = {
    employee_id: document.getElementById('emp_id').value,
    contract_code: document.getElementById('code').value,
    basic_salary: document.getElementById('salary').value,
    start_date: document.getElementById('start').value,
    end_date: document.getElementById('end').value || null
  }

  await ManagerAPI.renewContract(payload)
  closeModal()
  await loadContracts()
  alert('Gia hạn hợp đồng thành công')
}

document.getElementById('close-modal').addEventListener('click', closeModal)
document.getElementById('cancel-renew').addEventListener('click', closeModal)
document.getElementById('submit-renew').addEventListener('click', submitRenew)

loadContracts()