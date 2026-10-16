
'use strict';
const adminPage=location.pathname.includes('admin');
let stock=[],editing=false,ocrBusy=false,editorMetadata={};
function checkRole(){if(!principal||!(adminPage?principal.role==='admin':['admin','staff'].includes(principal.role))){throw new Error('Cần đăng nhập '+(adminPage?'Admin':'Staff/Admin'));}}
async function refreshStock(){
  checkRole();stock=await api('/api/manage/accounts');
  $('stock').innerHTML=stock.map(n=>`<tr><td>${escapeHTML(n.ma_nick)}</td><td>${escapeHTML(n.ma_game)}</td><td>${vnd(n.gia_ban)}</td><td>${escapeHTML(n.trang_thai)}</td><td><button class="small" data-edit="${escapeHTML(n.ma_nick)}">Sửa / OCR</button>${adminPage?` <button class="small danger" data-delete="${escapeHTML(n.ma_nick)}">Xóa</button>`:''}</td></tr>`).join('')||'<tr><td colspan="5">Kho đang trống.</td></tr>';
}
function resetEditor(){
  editing=false;$('nick-form').reset();
  editorMetadata={ngay_nhap_kho:new Date().toISOString().slice(0,10),SkinHiem:[]};loadAttributes(editorMetadata);
  $('nick-form').elements.ma_nick.readOnly=false;$('editor-title').textContent='Nhập nick mới';
}
function loadEditor(nick){
  editing=true;const form=$('nick-form');
  for(const field of ['ma_nick','ma_game','ma_ncc','gia_ban','trang_thai','anh_dinh_kem_url','mat_khau_game','email_khoi_phuc'])if(form.elements[field])form.elements[field].value=nick[field]??'';
  editorMetadata=structuredClone(nick.thong_tin_chi_tiet||{});loadAttributes(editorMetadata);
  form.elements.ma_nick.readOnly=true;$('editor-title').textContent='Sửa nick '+nick.ma_nick;
}
function splitTags(value){return value.split(/[,\n]/).map(x=>x.trim()).filter(Boolean);}
function loadAttributes(info){
  const form=$('nick-form');form.elements.rank.value=info.Rank||'';
  form.elements.skin_names.value=Array.isArray(info.SkinHiem)?info.SkinHiem.join(', '):'';
  form.elements.weapon_names.value=Array.isArray(info.VuKhi)?info.VuKhi.join(', '):'';
  form.elements.inventory_date.value=info.ngay_nhap_kho||'';
  renderResult('attribute-preview',info);
}
$('reset-editor').onclick=resetEditor;
$('refresh-stock').onclick=refreshStock;
$('stock').onclick=async event=>{
  if(ocrBusy)return;
  const edit=event.target.closest('[data-edit]'),remove=event.target.closest('[data-delete]');
  if(edit){loadEditor(stock.find(n=>n.ma_nick===edit.dataset.edit));$('nick-form').scrollIntoView({behavior:'smooth'});}
  if(remove&&await confirmAction('Xóa '+remove.dataset.delete+'? Đơn đã phát sinh sẽ bị FK RESTRICT chặn.')){
    renderResult('operation-output',await api('/api/admin/accounts/'+encodeURIComponent(remove.dataset.delete)+'/delete','DELETE'));await refreshStock();
  }
};
$('nick-form').onsubmit=async event=>{
  event.preventDefault();checkRole();if(ocrBusy)return;const button=event.submitter;button.disabled=true;
  try{
    const data=Object.fromEntries(new FormData(event.target));data.gia_ban=Number(data.gia_ban);
    data.thong_tin_chi_tiet={...editorMetadata,Rank:data.rank,SkinHiem:splitTags(data.skin_names),VuKhi:splitTags(data.weapon_names),ngay_nhap_kho:data.inventory_date||editorMetadata.ngay_nhap_kho};
    for(const key of ['rank','skin_names','weapon_names','inventory_date'])delete data[key];
    for(const field of ['anh_dinh_kem_url','email_khoi_phuc','ma_ncc'])if(data[field]==='')data[field]=null;
    if(data.mat_khau_game==='')delete data.mat_khau_game;
    const id=data.ma_nick;
    if(editing){delete data.ma_nick;if(!adminPage)delete data.ma_game;}
    const result=await api(editing?'/api/accounts/'+encodeURIComponent(id)+'/update':'/api/accounts/create',editing?'PUT':'POST',data);
    renderResult('operation-output',result);toast('Đã lưu nick');await refreshStock();loadEditor(stock.find(n=>n.ma_nick===id));
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
  renderResult('operation-output','EasyOCR đang xử lý ảnh; giữ nguyên ngày nhập kho và metadata…');
  try{
    const image=file?await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);}):url;
    if(epoch!==identityEpoch)throw new StaleRequest('Phiên đã thay đổi');
    const result=await api('/api/accounts/'+encodeURIComponent(id)+'/ocr','POST',{image_url:image});
    await refreshStock();
    const latest=stock.find(n=>n.ma_nick===id);
    if(latest)loadEditor(latest);
    renderResult('operation-output',result);
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
    event.preventDefault();if(!await confirmAction('Đã đối chiếu bằng chứng chuyển khoản và mã khách?'))return;
    renderResult('operation-output',await api('/api/staff/recheck-sepay','POST',Object.fromEntries(new FormData(event.target))));await refreshTransactions();
  };
  $('copilot-form').onsubmit=async event=>{event.preventDefault();renderResult('operation-output',await api('/api/staff/ai6-reconcile-assistant','POST',{prompt:$('copilot-input').value}));};
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
