
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
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));
    return data;
  }catch(error){
    if(error.name==='AbortError'||(!publicRead&&epoch!==identityEpoch))throw new StaleRequest('Yêu cầu cũ đã được hủy');
    throw error;
  }finally{pendingRequests.delete(controller);}
}
function showDialog(id){$(id).showModal();}
function printOutput(id,data){$(id).textContent=typeof data==='string'?data:JSON.stringify(data,null,2);}
function paintIdentity(){
  $('welcome').textContent=principal?principal.username+' · '+principal.role+(principal.ma_kh?' · '+principal.ma_kh:''):'Khách tham quan';
  $('login-button').textContent=principal?'Đổi tài khoản':'Đăng nhập';
  $('logout-button').classList.toggle('hidden',!principal);
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
}
function initCommon(){
  $('login-button').onclick=()=>showDialog('login-dialog');
  $('logout-button').onclick=async()=>{
    const token=sessionStorage.getItem('shop_token');
    principal=null;sessionStorage.removeItem('shop_token');purgePrivateState();
    $('welcome').textContent='Đang đăng xuất…';$('logout-button').disabled=true;
    try{await fetch('/api/auth/logout',{method:'POST',headers:token?{Authorization:'Bearer '+token}:{},signal:AbortSignal.timeout(10000)});}
    catch{toast('Đã xóa phiên cục bộ; không liên lạc được máy chủ.',true);}
    finally{$('logout-button').disabled=false;paintIdentity();}
  };
  $('login-form').onsubmit=async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try{
      const result=await api('/api/auth/login','POST',{username:$('login-user').value,password:$('login-password').value});
      purgePrivateState();sessionStorage.setItem('shop_token',result.token);principal=result.principal;
      paintIdentity();toast('Đăng nhập thành công');
      const next=new URLSearchParams(location.search).get('next');
      if((next==='/staff.html'&&['staff','admin'].includes(principal.role))||(next==='/admin.html'&&principal.role==='admin'))location.assign(next);
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
}
