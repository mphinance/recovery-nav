(function(){
  var items=[].slice.call(document.querySelectorAll('#results li'));
  var geo=JSON.parse(document.getElementById('geo').textContent);
  var q=document.getElementById('q'),county=document.getElementById('county'),reviewed=document.getElementById('reviewed');
  var boxes=[].slice.call(document.querySelectorAll('.chips input[type=checkbox]')).filter(function(b){return b.id!=='reviewed'});
  var map=null,markers={};
  function init(){
    if(!window.L)return;
    map=L.map('map',{scrollWheelZoom:false}).setView([43.25,-88.0],9);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
    Object.keys(geo).forEach(function(id){var g=geo[id];var m=L.marker([g.lat,g.lon]).addTo(map);m.bindPopup('<a href="f/'+id+'.html">'+g.name+'</a><br>'+g.city);markers[id]=m;});
  }
  function apply(){
    var term=q.value.trim().toLowerCase(),c=county.value,lv=boxes.filter(function(b){return b.checked}).map(function(b){return b.value}),n=0,pts=[];
    items.forEach(function(li){
      var ok=(!term||li.dataset.name.indexOf(term)>-1)&&(!c||li.dataset.county===c)&&(!reviewed.checked||li.dataset.reviewed==='1')&&(!lv.length||lv.some(function(x){return li.dataset.levels.split(' ').indexOf(x)>-1}));
      li.hidden=!ok;if(ok){n++;if(markers[li.dataset.id])pts.push(markers[li.dataset.id].getLatLng());}
      var m=markers[li.dataset.id];if(m&&map){if(ok&&!map.hasLayer(m))m.addTo(map);if(!ok&&map.hasLayer(m))map.removeLayer(m);}
    });
    document.getElementById('count').textContent=n+' of '+items.length+' programs';
    document.getElementById('empty').hidden=n>0;
    if(map&&pts.length)map.fitBounds(L.latLngBounds(pts).pad(.2),{maxZoom:13});
  }
  [q,county,reviewed].concat(boxes).forEach(function(el){el.addEventListener('input',apply)});
  var layout=document.getElementById('layout'),tl=document.getElementById('tab-list'),tm=document.getElementById('tab-map');
  function view(v){layout.dataset.view=v;tl.setAttribute('aria-pressed',v==='list');tm.setAttribute('aria-pressed',v==='map');if(v==='map'&&map)setTimeout(function(){map.invalidateSize()},50);}
  tl.addEventListener('click',function(){view('list')});tm.addEventListener('click',function(){view('map')});
  init();apply();
})();
