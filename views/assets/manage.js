
'use strict';
const adminPage=location.pathname.includes('admin');
let stock=[],editing=false,ocrBusy=false;
function checkRole(){if(!principal||!(adminPage?principal.role==='admin':['admin','staff'].includes(principal.role))){throw new Error('Cần đăng nhập '+(adminPage?'Admin':'Staff/Admin'));}}
async function refreshStock(){
  checkRole();stock=await api('/api/manage/accounts');
  $('stock').innerHTML=stock.map(n=>`<tr><td>${escapeHTML(n.ma_nick)}</td><td>${escapeHTML(n.ma_game)}</td><td>${vnd(n.gia_ban)}</td><td>${escapeHTML(n.trang_thai)}</td><td><button class="small" data-edit="${escapeHTML(n.ma_nick)}">Sửa / OCR</button>${adminPage?` <button class="small danger" data-delete="${escapeHTML(n.ma_nick)}">Xóa</button>`:''}</td></tr>`).join('')||'<tr><td colspan="5">Kho đang trống.</td></tr>';
}
function resetEditor(){
  editing=false;$('nick-form').reset();
  $('nick-form').elements.thong_tin_chi_tiet.value=JSON.stringify({ngay_nhap_kho:new Date().toISOString().slice(0,10),SkinHiem:[]},null,2);
  $('nick-form').elements.ma_nick.readOnly=false;$('editor-title').textContent='Nhập nick mới';
}
function loadEditor(nick){
  editing=true;const form=$('nick-form');
  for(const field of ['ma_nick','ma_game','ma_ncc','gia_ban','trang_thai','anh_dinh_kem_url','mat_khau_game','email_khoi_phuc'])if(form.elements[field])form.elements[field].value=nick[field]??'';
  form.elements.thong_tin_chi_tiet.value=JSON.stringify(nick.thong_tin_chi_tiet||{},null,2);
  form.elements.ma_nick.readOnly=true;$('editor-title').textContent='Sửa nick '+nick.ma_nick;
}
$('reset-editor').onclick=resetEditor;
$('refresh-stock').onclick=refreshStock;
$('stock').onclick=async event=>{
  if(ocrBusy)return;
  const edit=event.target.closest('[data-edit]'),remove=event.target.closest('[data-delete]');
  if(edit){loadEditor(stock.find(n=>n.ma_nick===edit.dataset.edit));$('nick-form').scrollIntoView({behavior:'smooth'});}
  if(remove&&confirm('Xóa '+remove.dataset.delete+'? Đơn đã phát sinh sẽ bị FK RESTRICT chặn.')){
    printOutput('operation-output',await api('/api/admin/accounts/'+encodeURIComponent(remove.dataset.delete)+'/delete','DELETE'));await refreshStock();
  }
};
$('nick-form').onsubmit=async event=>{
  event.preventDefault();checkRole();if(ocrBusy)return;const button=event.submitter;button.disabled=true;
  try{
    const data=Object.fromEntries(new FormData(event.target));data.gia_ban=Number(data.gia_ban);data.thong_tin_chi_tiet=JSON.parse(data.thong_tin_chi_tiet);
    if(!data.thong_tin_chi_tiet||Array.isArray(data.thong_tin_chi_tiet)||typeof data.thong_tin_chi_tiet!=='object')throw new Error('JSONB phải là object');
    for(const field of ['anh_dinh_kem_url','email_khoi_phuc','ma_ncc'])if(data[field]==='')data[field]=null;
    if(data.mat_khau_game==='')delete data.mat_khau_game;
    const id=data.ma_nick;
    if(editing){delete data.ma_nick;if(!adminPage)delete data.ma_game;}
    const result=await api(editing?'/api/accounts/'+encodeURIComponent(id)+'/update':'/api/accounts/create',editing?'PUT':'POST',data);
    printOutput('operation-output',result);toast('Đã lưu nick');await refreshStock();loadEditor(stock.find(n=>n.ma_nick===id));
  }finally{button.disabled=false;}
};
$('ocr-button').onclick=async()=>{
  checkRole();if(ocrBusy)return;
  const id=$('nick-form').elements.ma_nick.value,file=$('ocr-file').files[0];
  const url=$('nick-form').elements.anh_dinh_kem_url.value.trim();
  if(!editing||!id||(!file&&!url))throw new Error('Lưu/chọn nick trước, rồi chọn file hoặc dán URL ảnh');
  if(file&&file.size>5*1024*1024)throw new Error('Ảnh tối đa 5MB');
  ocrBusy=true;const epoch=identityEpoch;
  const controls=[...$('nick-form').querySelectorAll('input,select,textarea,button'),$('ocr-button'),$('ocr-file')];
  controls.forEach(control=>control.disabled=true);
  printOutput('operation-output','EasyOCR đang xử lý ảnh; giữ nguyên ngày nhập kho và metadata…');
  try{
    const image=file?await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);}):url;
    if(epoch!==identityEpoch)throw new StaleRequest('Phiên đã thay đổi');
    const result=await api('/api/accounts/'+encodeURIComponent(id)+'/ocr','POST',{image_url:image});
    await refreshStock();
    const latest=stock.find(n=>n.ma_nick===id);
    if(latest)loadEditor(latest);
    printOutput('operation-output',result);
    toast('OCR đã cập nhật JSONB trong form và database');
  }finally{ocrBusy=false;controls.forEach(control=>control.disabled=false);}
};
if(!adminPage){
  async function refreshTransactions(){
    checkRole();const query=new URLSearchParams();
    if($('filter-customer').value.trim())query.set('ma_kh',$('filter-customer').value.trim());
    if($('filter-event').value.trim())query.set('ma_giao_dich',$('filter-event').value.trim());
    const result=await api('/api/staff/transactions?'+query.toString());
    $('staff-transactions').innerHTML=result.map(n=>'<tr>'+['ma_giao_dich','ma_kh','so_tien','phuong_thuc','trang_thai','ngay_tao'].map(k=>'<td>'+escapeHTML(k==='so_tien'?vnd(n[k]):n[k])+'</td>').join('')+'</tr>').join('');
  }
  $('refresh-transactions').onclick=refreshTransactions;
  $('transaction-filter').onsubmit=event=>{event.preventDefault();refreshTransactions();};
  $('recheck-form').onsubmit=async event=>{
    event.preventDefault();if(!confirm('Đã đối chiếu bằng chứng chuyển khoản và mã khách?'))return;
    printOutput('operation-output',await api('/api/staff/recheck-sepay','POST',Object.fromEntries(new FormData(event.target))));await refreshTransactions();
  };
  $('copilot-form').onsubmit=async event=>{event.preventDefault();printOutput('operation-output',await api('/api/staff/ai6-reconcile-assistant','POST',{prompt:$('copilot-input').value}));};
}else{
  document.querySelectorAll('[data-ai]').forEach(button=>button.onclick=async()=>{
    checkRole();button.disabled=true;try{printOutput('operation-output',await api(button.dataset.ai,button.dataset.method||'POST'));await refreshStock();}finally{button.disabled=false;}
  });
  $('ai1-card').onclick=()=>{$('ocr-file').closest('details').open=true;$('ocr-file').scrollIntoView({behavior:'smooth'});$('ocr-file').focus();};
  $('ai4-card').onclick=()=>showDialog('admin-chat-dialog');
  $('ai6-card').onclick=()=>showDialog('admin-reconcile-dialog');
  $('ai8-card').onclick=()=>{$('dispute-form').scrollIntoView({behavior:'smooth'});$('dispute-form').elements.ma_nick.focus();};
  $('admin-chat-form').onsubmit=async event=>{event.preventDefault();printOutput('admin-chat-output',await api('/api/chat/nl2sql','POST',{prompt:$('admin-chat-prompt').value}));};
  $('admin-reconcile-form').onsubmit=async event=>{event.preventDefault();printOutput('admin-reconcile-output',await api('/api/staff/ai6-reconcile-assistant','POST',{prompt:$('admin-reconcile-prompt').value}));};
  $('fraud-button').onclick=async()=>{
    const id=$('nick-form').elements.ma_nick.value;if(!id)throw new Error('Chọn nick trong form trước');if(!confirm('Khóa tranh chấp nick '+id+'?'))return;
    printOutput('operation-output',await api('/api/admin/lock-fraud/'+encodeURIComponent(id),'POST'));await refreshStock();
  };
  $('vacuum-button').onclick=async()=>{printOutput('operation-output',await api('/api/admin/run-vacuum','POST',{table:'tai_khoan_game'}));};
  $('dispute-form').onsubmit=async event=>{
    event.preventDefault();const form=event.target;printOutput('operation-output',await api('/api/admin/ai8-evaluate-dispute','POST',{ma_nick:form.elements.ma_nick.value,evidence_count:Number(form.elements.evidence_count.value),seller_unresponsive:form.elements.seller_unresponsive.checked,recovery_changed:form.elements.recovery_changed.checked}));
  };
}
window.addEventListener('identity-reset',()=>{
  stock=[];resetEditor();$('operation-output').textContent='';
  if($('transaction-filter'))$('transaction-filter').reset();
  if($('copilot-form'))$('copilot-form').reset();
  for(const id of ['admin-chat-output','admin-reconcile-output'])if($(id))$(id).textContent='';
});
window.addEventListener('identity',async()=>{
  $('stock').textContent='';resetEditor();
  if(!principal){$('role-message').textContent='Đăng nhập để sử dụng bàn làm việc.';return;}
  try{checkRole();$('role-message').textContent='Phiên '+principal.username+' · '+principal.role+' · API và quyền database được kiểm tra ở máy chủ.';await gamesReady;await refreshStock();}catch(error){if(!(error instanceof StaleRequest))$('role-message').textContent=error.message;}
});
async function loadGames(){const games=await api('/api/games');games.forEach(g=>{const option=document.createElement('option');option.value=g.ma_game;option.textContent=g.ten_game;$('editor-game').append(option);});}
const gamesReady=loadGames();
initCommon();
