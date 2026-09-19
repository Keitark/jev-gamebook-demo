/* Generated illustration plates for The Ashen Gate. Presentation-only. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const PLATES = Object.freeze({
    '1':  {src:'/static/plates/crossroads.svg', alt:'霧の分かれ道に立つ古い石標と枯れ木の版画'},
    '3':  {src:'/static/plates/chapel.svg', alt:'崩れた礼拝堂の入口と灯火を持つ人物の版画'},
    '4':  {src:'/static/plates/stranger.svg', alt:'川辺の宿で灯火のそばに座る謎めいた旅人の版画'},
    '5':  {src:'/static/plates/wolf.svg', alt:'月夜の森道に立ちはだかる狼の版画'},
    '7':  {src:'/static/plates/ferryman.svg', alt:'霧の川を小舟で渡る渡し守の版画'},
    '8':  {src:'/static/plates/gate.svg', alt:'霧に包まれた古い石の城門と川辺の版画'},
    '9':  {src:'/static/plates/bridge.svg', alt:'崩落した石橋と峡谷の灯籠を描いた版画'},
    '12': {src:'/static/plates/city.svg', alt:'湿地の向こうに見える灯火の城門都市の版画'},
  });
  function clear(){ document.querySelectorAll('.passage-plate').forEach(node => node.remove()); }
  function render(run){
    clear();
    if(!run || run.book !== 'demo') return;
    const plate=PLATES[String(run.current)], story=$('storyText');
    if(!plate || !story) return;
    const figure=document.createElement('figure'); figure.className='passage-plate'; figure.dataset.section=String(run.current);
    const img=document.createElement('img'); img.src=plate.src; img.alt=plate.alt; img.loading='eager'; img.decoding='async'; img.draggable=false;
    figure.append(img);
    const paragraphs=story.querySelectorAll(':scope > p');
    if(paragraphs.length>1) paragraphs[0].after(figure); else story.append(figure);
  }
  const base=window.ReaderUI?.decorate;
  if(base){ window.ReaderUI.decorate=function(run){ base.call(window.ReaderUI,run); render(run); }; }
  window.ReaderIllustrations={render,clear,plates:PLATES};
})();