
'use strict';
let catalogData=[], favorites=new Set(), historyData=[], cartData=[];
let depositId='';let chatBusy=false;
function requireCustomer(){if(!principal||principal.role!=='user'){showDialog('login-dialog');return false;}return true;}
function renderCatalog(){
  const selected=$('game-filter').value, maximum=Number($('price-filter').value);
  $('price-label').textContent=vnd(maximum);
  const items=catalogData.filter(n=>(!selected||n.ma_game===selected)&&Number(n.gia_ban)<=maximum&&(!$('favorite-filter').checked||favorites.has(n.ma_nick)));
  $('count').textContent=items.length+' tài khoản';
  $('catalog').innerHTML=items.map(n=>productCard(n,`<div class="actions"><button class="small" data-action="heart" data-id="${escapeHTML(n.ma_nick)}" aria-label="Yêu thích">${favorites.has(n.ma_nick)?'♥':'♡'}</button><button class="small primary" data-action="cart" data-id="${escapeHTML(n.ma_nick)}">Giữ chỗ 15p</button><button class="small" data-action="credentials" data-id="${escapeHTML(n.ma_nick)}">Xem Mật Khẩu</button></div>`)).join('')||'<div class="panel empty">Chưa có nick phù hợp. Thử đổi game hoặc ngân sách.</div>';
}
async function loadCatalog(){catalogData=await api('/api/accounts');renderCatalog();}
async function refreshPersonal(){
  if(!principal||principal.role!=='user'){favorites=new Set();$('balance').textContent='Số dư ví: —';$('cart').textContent='Đăng nhập tài khoản khách để giữ chỗ.';$('orders').textContent='Chưa có phiên khách hàng.';renderCatalog();return;}
  const [profile,wishlist,cart,orders]=await Promise.all([api('/api/user/profile/'+encodeURIComponent(principal.ma_kh)),api('/api/user/wishlist'),api('/api/user/cart'),api('/api/user/orders')]);
  $('balance').textContent='Số dư ví: '+vnd(profile.so_du_vi);
  favorites=new Set(wishlist.map(x=>x.ma_nick));cartData=cart.map(x=>({...x,deadline:Date.now()+Number(x.seconds_left)*1000}));renderCart();
  $('orders').innerHTML=orders.map(o=>`<div class="entry"><div class="row between"><strong>${escapeHTML(o.ma_nick)}</strong><span>${vnd(o.tong_tien)}</span></div><small>${escapeHTML(o.trang_thai)}</small><button class="small" data-credentials="${escapeHTML(o.ma_nick)}">Xem Mật Khẩu</button></div>`).join('')||'Bạn chưa mua nick nào.';
  renderCatalog();
}
function renderCart(){
  $('cart').innerHTML=cartData.map(n=>`<div class="entry"><div class="row between"><strong>${escapeHTML(n.ma_nick)}</strong><span>${vnd(n.gia_ban)}</span></div><small data-deadline="${n.deadline}"></small><button class="small" data-remove="${escapeHTML(n.ma_nick)}">Bỏ giữ chỗ</button></div>`).join('')||'Giỏ hàng trống.';
  updateCountdown();
}
function updateCountdown(){document.querySelectorAll('[data-deadline]').forEach(e=>{const seconds=Math.max(0,Math.floor((Number(e.dataset.deadline)-Date.now())/1000));e.textContent=seconds?`Còn ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`:'Đã hết hạn giữ chỗ';});}
async function showCredentials(id){if(!requireCustomer())return;try{const result=await api('/api/accounts/'+encodeURIComponent(id)+'/credentials');renderResult('credentials-content',result);showDialog('credentials-dialog');}catch(error){if(!(error instanceof StaleRequest))toast(error.message,true);}}
$('catalog').onclick=async event=>{
  const button=event.target.closest('[data-action]');if(!button)return;
  if(!requireCustomer())return;const id=button.dataset.id;button.disabled=true;
  try{
    if(button.dataset.action==='heart'){const exists=favorites.has(id);await api('/api/user/wishlist'+(exists?'/'+encodeURIComponent(id):''),exists?'DELETE':'POST',exists?undefined:{ma_nick:id});await refreshPersonal();}
    if(button.dataset.action==='cart'){await api('/api/user/cart/add','POST',{ma_nick:id});toast('Đã giữ chỗ 15 phút');await Promise.all([loadCatalog(),refreshPersonal()]);}
    if(button.dataset.action==='credentials')await showCredentials(id);
  }finally{button.disabled=false;}
};
$('orders').onclick=event=>{const button=event.target.closest('[data-credentials]');if(button)showCredentials(button.dataset.credentials);};
$('cart').onclick=async event=>{const button=event.target.closest('[data-remove]');if(!button)return;await api('/api/user/cart/'+encodeURIComponent(button.dataset.remove),'DELETE');await Promise.all([loadCatalog(),refreshPersonal()]);};
$('checkout-button').onclick=async()=>{if(!requireCustomer())return;const button=$('checkout-button');button.disabled=true;try{const result=await api('/api/user/cart/checkout','POST');toast('Thanh toán thành công: '+vnd(result.total));await Promise.all([loadCatalog(),refreshPersonal()]);}finally{button.disabled=false;}};
function updateDeposit(){
  const card=$('deposit-method').value==='card';$('card-fields').classList.toggle('hidden',!card);$('sepay-fields').classList.toggle('hidden',card);
  $('card-serial').required=card;$('card-code').required=card;
  const amount=$('deposit-amount').value,description=$('deposit-description').value;
  $('qr-image').src='https://qr.sepay.vn/img?acc=0987654321&bank=MBBank&amount='+encodeURIComponent(amount)+'&des='+encodeURIComponent(description);
  $('deposit-event').textContent='Mã yêu cầu chống trùng: '+depositId;
}
$('deposit-button').onclick=()=>{if(!requireCustomer())return;depositId=crypto.randomUUID();$('deposit-description').value='NAP '+principal.ma_kh;updateDeposit();showDialog('deposit-dialog');};
$('deposit-method').onchange=()=>{depositId=crypto.randomUUID();updateDeposit();};
$('deposit-amount').onchange=()=>{depositId=crypto.randomUUID();updateDeposit();};
$('deposit-description').oninput=()=>{depositId=crypto.randomUUID();updateDeposit();};
['card-serial','card-code'].forEach(id=>$(id).oninput=()=>{depositId=crypto.randomUUID();updateDeposit();});
$('deposit-form').onsubmit=async event=>{
  event.preventDefault();if(!requireCustomer())return;$('deposit-submit').disabled=true;
  try{const result=await api('/api/user/deposit/'+$('deposit-method').value,'POST',{amount:$('deposit-amount').value,event_id:depositId,description:$('deposit-description').value,serial:$('card-serial').value,card:$('card-code').value});toast(result.trang_thai==='Cho_duyet'?'Sai cú pháp: giao dịch đang chờ Staff đối soát':'Đã nạp tiền thành công');$('deposit-dialog').close();$('card-code').value='';await refreshPersonal();}finally{$('deposit-submit').disabled=false;}
};
function renderHistory(){const filter=$('history-filter').value;$('history-list').innerHTML=historyData.filter(n=>!filter||n.loai_gd===filter).map(n=>`<div class="entry"><strong>${escapeHTML(n.loai_gd)} · ${escapeHTML(n.chieu_bien_dong)}${vnd(n.so_tien)}</strong><p><small>${escapeHTML(n.ma_gd)} · ${escapeHTML(n.trang_thai)}</small></p><button class="small" data-receipt="${escapeHTML(n.ma_gd)}">Chi tiết / Biên lai</button></div>`).join('')||'<p>Chưa có giao dịch.</p>';}
$('history-button').onclick=async()=>{if(!requireCustomer())return;historyData=await api('/api/user/transactions/'+encodeURIComponent(principal.ma_kh));renderHistory();showDialog('history-dialog');};
$('history-filter').onchange=renderHistory;
$('history-list').onclick=async event=>{const button=event.target.closest('[data-receipt]');if(button){renderResult('receipt-content',await api('/api/user/transaction-detail/'+encodeURIComponent(button.dataset.receipt)));showDialog('receipt-dialog');}};
async function askBot(question){
  if(chatBusy||!question.trim())return;chatBusy=true;const log=$('chatlog');const user=document.createElement('div');user.className='bubble user';user.textContent=question;log.append(user);const answer=document.createElement('div');answer.className='bubble';answer.textContent='AI đang phân tích điều kiện JSONB…';log.append(answer);log.scrollTop=log.scrollHeight;
  try{const result=await api('/api/chat/nl2sql','POST',{prompt:question});answer.id='chat-result-'+crypto.randomUUID();renderResult(answer.id,result);}catch(error){answer.textContent=error.message;}finally{chatBusy=false;log.scrollTop=log.scrollHeight;}
}
$('chat-form').onsubmit=event=>{event.preventDefault();const question=$('chat-input').value;$('chat-input').value='';askBot(question);};
document.querySelectorAll('.quick').forEach(b=>b.onclick=()=>askBot(b.dataset.prompt));
$('register-form').onsubmit=async event=>{event.preventDefault();const result=await api('/api/auth/register','POST',Object.fromEntries(new FormData(event.target)));toast(result.message);showDialog('login-dialog');};
['game-filter','price-filter','favorite-filter'].forEach(id=>$(id).addEventListener('input',renderCatalog));
window.addEventListener('identity-reset',()=>{chatBusy=false;$('chatlog').textContent='Hãy cho tôi biết game, ngân sách và skin/vũ khí bạn muốn tìm.';favorites=new Set();historyData=[];cartData=[];depositId='';$('balance').textContent='Số dư ví: —';$('deposit-form').reset();$('qr-image').removeAttribute('src');});
window.addEventListener('identity',()=>refreshPersonal());
async function start(){const games=await api('/api/games');games.forEach(game=>{const option=document.createElement('option');option.value=game.ma_game;option.textContent=game.ten_game;$('game-filter').append(option);});await loadCatalog();}
initCommon();start();setInterval(updateCountdown,1000);
setInterval(()=>{Promise.all([loadCatalog(),refreshPersonal()]).catch(error=>toast(error.message,true));},30000);
