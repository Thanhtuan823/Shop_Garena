
'use strict';
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const vnd = value => new Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'}).format(Number(value));
let principal = null;
let identityEpoch = 0;
const pendingRequests = new Set();
class StaleRequest extends Error {}
function toast(message, error=false){
  const box=document.createElement('div');box.className='toast'+(error?' error':'');box.role=error?'alert':'status';box.textContent=message;document.body.append(box);setTimeout(()=>box.remove(),6500);
}
function purgePrivateState(){
  identityEpoch++;
  for(const controller of pendingRequests)controller.abort();
  pendingRequests.clear();
  document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
  for(const id of ['credentials-content','receipt-content','history-list','staff-transactions','stock','operation-output','orders','cart']){
    if($(id))$(id).textContent='';
  }
  document.querySelectorAll('input[type=password],#card-code,#card-serial,#ocr-file').forEach(input=>input.value='');
  document.querySelectorAll('.toast').forEach(element=>element.remove());
  window.dispatchEvent(new Event('identity-reset'));
}
async function api(path, method='GET', body){
  const epoch=identityEpoch,controller=new AbortController();
  const publicRead=method==='GET'&&['/api/accounts','/api/games'].includes(new URL(path,location.origin).pathname);
  const headers={};const token=sessionStorage.getItem('shop_token');
  if(token&&!publicRead)headers.Authorization='Bearer '+token;
  if(body!==undefined)headers['Content-Type']='application/json';
  if(!publicRead)pendingRequests.add(controller);
  try{
    const response=await fetch(path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,cache:'no-store'});
    const type=response.headers.get('content-type')||'';
    const data=type.includes('application/json')?await response.json():{detail:'Máy chủ không trả JSON hợp lệ; kiểm tra đúng cổng/API.'};
    if(!publicRead&&epoch!==identityEpoch)throw new StaleRequest('Phiên đã thay đổi');
    if(!response.ok){
      const messages={401:'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.',403:'Bạn không có quyền thực hiện thao tác này.',422:'Thông tin chưa hợp lệ. Kiểm tra các trường trong biểu mẫu.',500:'Máy chủ đang gặp sự cố. Vui lòng thử lại.',503:'Dịch vụ chưa sẵn sàng. Vui lòng thử lại sau.'};
      throw new Error(typeof data.detail==='string'?data.detail:(messages[response.status]||'Không thể xử lý yêu cầu. Vui lòng thử lại.'));
    }
    return data;
  }catch(error){
    if(error.name==='AbortError'||(!publicRead&&epoch!==identityEpoch))throw new StaleRequest('Yêu cầu cũ đã được hủy');
    throw error;
  }finally{pendingRequests.delete(controller);}
}
function showDialog(id){$(id).showModal();}
const fieldLabels={ma_nick:'Mã nick',ma_game:'Game',ma_kh:'Khách hàng',ma_gd:'Mã giao dịch',ma_giao_dich:'Mã giao dịch',ho_ten:'Họ tên',Rank:'Rank',SkinHiem:'Skin nổi bật',VuKhi:'Vũ khí',DoiHinh:'Đội hình',SoTuong:'Số tướng',SoSkin:'Số skin',ngay_nhap_kho:'Ngày nhập kho',thong_tin_chi_tiet:'Thuộc tính tài khoản',mat_khau_game:'Mật khẩu game',email_khoi_phuc:'Email khôi phục',so_tien:'Số tiền',tong_tien:'Tổng tiền',phuong_thuc:'Phương thức',trang_thai:'Trạng thái',ngay_tao:'Ngày tạo',loai_gd:'Loại giao dịch',chieu_bien_dong:'Chiều biến động',chi_tiet:'Chi tiết',message:'Thông báo',rows:'Số dòng',updated:'Đã cập nhật',valid:'Hợp lệ',invalid:'Bị loại',inserted:'Đã nhập',rejected:'Bị loại',loaded:'Đã nạp',reason:'Giải thích',ocr_text:'Nội dung đọc được',confidence:'Độ khớp',confidence_score:'Độ tin cậy',recommendation:'Khuyến nghị',table:'Bảng',live:'Dòng đang sử dụng',dead:'Dòng chết',dead_ratio_pct:'Tỷ lệ dòng chết',last_autovacuum:'Autovacuum gần nhất',last_autoanalyze:'Autoanalyze gần nhất',requires_human_review:'Cần người xác nhận',executed:'Đã thực hiện',proposed_refund:'Số tiền đề xuất hoàn',recommend_refund:'Đề xuất hoàn tiền',risk_score:'Điểm rủi ro',automatic_credit:'Tự cộng tiền',reply:'Gợi ý trả lời',affected:'Số nick cập nhật',voucher:'Voucher',ma_voucher_tang:'Mã voucher',churn_risk_score:'Điểm nguy cơ rời bỏ',total:'Tổng tiền',balance:'Số dư'};
function fieldTitle(key){return fieldLabels[key]||key.replaceAll('_',' ');}
function valueHTML(value,key=''){
  if(value===null||value===undefined||value==='')return '<span class="muted">Chưa có</span>';
  if(typeof value==='boolean')return value?'Có':'Không';
  if(Array.isArray(value))return value.length?value.map(item=>typeof item==='object'?factsHTML(item):`<span class="chip">${escapeHTML(item)}</span>`).join(''):'<span class="muted">Chưa có</span>';
  if(typeof value==='object')return factsHTML(value);
  return escapeHTML(['so_tien','tong_tien','gia_ban','proposed_refund','total','balance'].includes(key)?vnd(value):value);
}
function factsHTML(data){return '<dl class="facts">'+Object.entries(data).map(([key,value])=>`<dt>${escapeHTML(fieldTitle(key))}</dt><dd>${valueHTML(value,key)}</dd>`).join('')+'</dl>';}
function productImage(n){
  const url=n.anh_dinh_kem_url||'';
  if(/^\/assets\/products\/[a-zA-Z0-9_-]+\.png$/.test(url))return url;
  return '/assets/games/logo_'+(/Free|FF/i.test(n.ten_game||n.ma_game)?'ff':/FC/i.test(n.ten_game||n.ma_game)?'fco':'lq')+'.png';
}
function productCard(n,actions=''){
  const info=n.thong_tin_chi_tiet||{};
  return `<article class="card result-card"><img class="product-image" src="${escapeHTML(productImage(n))}" alt="Ảnh minh họa ${escapeHTML(n.ma_nick)}" loading="lazy"><div class="card-body"><small>#${escapeHTML(n.ma_nick)}</small><h3>${escapeHTML(n.ten_game||n.ma_game)}</h3><div class="row between"><strong class="price">${vnd(n.gia_ban)}</strong><span class="badge">${escapeHTML(n.trang_thai)}</span></div><p class="muted">Rank: ${escapeHTML(info.Rank||'Chưa cập nhật')}</p><div>${['SkinHiem','VuKhi','DoiHinh'].flatMap(k=>Array.isArray(info[k])?info[k]:[]).map(x=>`<span class="chip">${escapeHTML(x)}</span>`).join('')}</div>${actions}</div></article>`;
}
function renderResult(id,data){
  const target=$(id);if(!target)return;
  if(typeof data==='string'){target.textContent=data;return;}
  if(Array.isArray(data)){
    if(!data.length){target.textContent='Không có kết quả phù hợp.';return;}
    if(data[0].ma_nick&&data[0].gia_ban!==undefined){target.innerHTML='<div class="cards">'+data.map(n=>productCard(n)).join('')+'</div>';return;}
    if(data[0].dead_ratio_pct!==undefined){
      target.innerHTML=data.map(row=>`<article class="result-card diagnostic-card"><h3>${escapeHTML(row.table)}</h3><p>Dòng chết: ${Number(row.dead_ratio_pct).toFixed(2)}% (ước lượng từ thống kê)</p><progress class="health-bar" max="100" value="${Math.min(100,Math.max(0,Number(row.dead_ratio_pct)))}" aria-label="Tỷ lệ dòng chết"></progress>${factsHTML(row)}</article>`).join('');return;
    }
    target.innerHTML=data.map(row=>'<article class="result-card">'+factsHTML(row)+'</article>').join('');return;
  }
  if(data.candidates){
    target.innerHTML='<h3>Khách hàng gần khớp</h3>'+data.candidates.map(n=>`<article class="result-card matching-card"><strong>${escapeHTML(n.ho_ten)} · ${escapeHTML(n.ma_kh)}</strong><p>Độ khớp: ${Number(n.confidence).toFixed(1)}%</p><progress class="health-bar" value="${Number(n.confidence)}" max="100" aria-label="Độ khớp"></progress></article>`).join('')+`<p>${escapeHTML(data.reply)}</p><small>Nhân viên phải xác minh trước khi cộng tiền.</small>`;return;
  }
  if(data.risk_score!==undefined){
    const risk=Math.min(100,Math.max(0,Number(data.risk_score)));
    target.innerHTML=`<article class="result-card verdict-card"><h3>Đánh giá tranh chấp · ${escapeHTML(data.ma_nick)}</h3><p class="${risk>80?'risk-high':'health-good'}">Điểm rủi ro theo quy tắc: ${risk}/100</p><progress class="risk-bar" value="${risk}" max="100" aria-label="Điểm rủi ro"></progress><h3>${data.recommend_refund?'Đề xuất hoàn '+vnd(data.proposed_refund):'Cần xác minh thêm bằng chứng'}</h3><p>${escapeHTML(data.reason)}</p><small>Đề xuất chưa thực hiện. Cần người có thẩm quyền duyệt.</small></article>`;return;
  }
  target.innerHTML='<article class="result-card">'+factsHTML(data)+'</article>';
}
function confirmAction(message){
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');const text=document.createElement('p');text.textContent=message;
    const actions=document.createElement('div');actions.className='confirm-actions';
    for(const [label,value] of [['Hủy',false],['Xác nhận',true]]){
      const button=document.createElement('button');button.textContent=label;
      if(value)button.className='primary';button.onclick=()=>{dialog.returnValue=value?'yes':'no';dialog.close();};actions.append(button);
    }
    dialog.append(text,actions);document.body.append(dialog);
    dialog.addEventListener('close',()=>{const yes=dialog.returnValue==='yes';dialog.remove();resolve(yes);},{once:true});dialog.showModal();
  });
}
function renderNavbarByRole(){
  const role=principal&&['user','staff','admin'].includes(principal.role)?principal.role:'guest';
  document.querySelectorAll('[data-nav-roles]').forEach(element=>{
    const allowed=element.dataset.navRoles.split(' ').includes(role);
    element.classList.toggle('hidden',!allowed);
  });
  $('login-button').classList.toggle('hidden',role==='user');
  $('logout-button').classList.toggle('hidden',role==='guest');
}
function redirectAfterLogin(){
  if(principal.role==='admin')location.assign('/admin.html');
  else if(principal.role==='staff')location.assign('/staff.html');
  else if(!['/','/index.html'].includes(location.pathname))location.assign('/index.html');
}
function paintIdentity(){
  $('welcome').textContent=principal?principal.username+' · '+principal.role+(principal.ma_kh?' · '+principal.ma_kh:''):'Khách tham quan';
  $('login-button').textContent=principal?'Đổi tài khoản':'Đăng nhập';
  renderNavbarByRole();
  window.dispatchEvent(new Event('identity'));
}
async function syncIdentity(){
  const epoch=identityEpoch;
  principal=null;
  if(sessionStorage.getItem('shop_token')){
    try{const user=await api('/api/auth/me');if(epoch!==identityEpoch)return;principal=user;}
    catch(error){if(error instanceof StaleRequest)return;sessionStorage.removeItem('shop_token');purgePrivateState();}
  }
  paintIdentity();
  const protectedRole=document.documentElement.dataset.protected;
  if(protectedRole){
    if(!principal||!(principal.role===protectedRole||(protectedRole==='staff'&&principal.role==='admin'))){location.replace('/index.html?error=unauthorized');return;}
    document.documentElement.classList.add('session-ready');
  }
}
function initCommon(){
  renderNavbarByRole();
  $('login-button').onclick=()=>showDialog('login-dialog');
  $('logout-button').onclick=async()=>{
    const token=sessionStorage.getItem('shop_token');
    principal=null;
    for(const storage of [localStorage,sessionStorage])for(const key of Object.keys(storage))if(key.startsWith('shop_'))storage.removeItem(key);
    purgePrivateState();
    renderNavbarByRole();
    $('welcome').textContent='Đang đăng xuất…';$('logout-button').disabled=true;
    try{await fetch('/api/auth/logout',{method:'POST',headers:token?{Authorization:'Bearer '+token}:{},signal:AbortSignal.timeout(10000)});}
    catch{toast('Đã xóa phiên cục bộ; không liên lạc được máy chủ.',true);}
    finally{$('logout-button').disabled=false;paintIdentity();location.replace('/');}
  };
  $('login-form').onsubmit=async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try{
      const result=await api('/api/auth/login','POST',{username:$('login-user').value,password:$('login-password').value});
      purgePrivateState();sessionStorage.setItem('shop_token',result.token);principal=result.principal;
      paintIdentity();toast('Đăng nhập thành công');
      redirectAfterLogin();
    }catch(error){if(!(error instanceof StaleRequest))toast(error.message,true);}
    finally{button.disabled=false;}
  };
  document.querySelectorAll('[data-close]').forEach(button=>button.onclick=()=>{
    const id=button.dataset.close;$(id).close();
    if(id==='credentials-dialog')$('credentials-content').textContent='';
    if(id==='receipt-dialog')$('receipt-content').textContent='';
  });
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('close',()=>{
    if(dialog.id==='credentials-dialog')$('credentials-content').textContent='';
    if(dialog.id==='receipt-dialog')$('receipt-content').textContent='';
  }));
  window.addEventListener('unhandledrejection',event=>{
    event.preventDefault();if(!(event.reason instanceof StaleRequest))toast(event.reason?.message||String(event.reason),true);
  });
  window.addEventListener('pagehide',purgePrivateState);
  window.addEventListener('pageshow',event=>{if(event.persisted)syncIdentity();});
  syncIdentity();
  if(new URLSearchParams(location.search).get('error')==='unauthorized')toast('Vui lòng đăng nhập đúng vai trò để mở trang này.',true);
}
