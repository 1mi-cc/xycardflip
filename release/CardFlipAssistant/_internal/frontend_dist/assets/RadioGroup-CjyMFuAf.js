import{b7 as oe,bE as te,bC as T,am as re,M as ne,bl as U,r as k,a7 as I,bi as V,K as A,ab as w,$ as F,a1 as R,a0 as S,Y as _,ag as $,k as ae,aZ as ie,D as E,a6 as M,U as de,L as se,n as D,av as H,a9 as le}from"./index-BSMS5bAg.js";import{u as P}from"./use-merged-state-fCj_4uQ6.js";import{g as ue}from"./get-slot-Bk_rJcZu.js";function ce(e){const{borderColor:o,primaryColor:t,baseColor:a,textColorDisabled:n,inputColorDisabled:d,textColor2:i,opacityDisabled:s,borderRadius:c,fontSizeSmall:g,fontSizeMedium:v,fontSizeLarge:m,heightSmall:b,heightMedium:x,heightLarge:p,lineHeight:C}=e;return Object.assign(Object.assign({},te),{labelLineHeight:C,buttonHeightSmall:b,buttonHeightMedium:x,buttonHeightLarge:p,fontSizeSmall:g,fontSizeMedium:v,fontSizeLarge:m,boxShadow:`inset 0 0 0 1px ${o}`,boxShadowActive:`inset 0 0 0 1px ${t}`,boxShadowFocus:`inset 0 0 0 1px ${t}, 0 0 0 2px ${T(t,{alpha:.2})}`,boxShadowHover:`inset 0 0 0 1px ${t}`,boxShadowDisabled:`inset 0 0 0 1px ${o}`,color:a,colorDisabled:d,colorActive:"#0000",textColor:i,textColorDisabled:n,dotColorActive:t,dotColorDisabled:o,buttonBorderColor:o,buttonBorderColorActive:t,buttonBorderColorHover:o,buttonColor:a,buttonColorActive:a,buttonTextColor:i,buttonTextColorActive:t,buttonTextColorHover:t,opacityDisabled:s,buttonBoxShadowFocus:`inset 0 0 0 1px ${t}, 0 0 0 2px ${T(t,{alpha:.3})}`,buttonBoxShadowHover:"inset 0 0 0 1px #0000",buttonBoxShadow:"inset 0 0 0 1px #0000",buttonBorderRadius:c})}const be={common:oe,self:ce},xe={name:String,value:{type:[String,Number,Boolean],default:"on"},checked:{type:Boolean,default:void 0},defaultChecked:Boolean,disabled:{type:Boolean,default:void 0},label:String,size:String,onUpdateChecked:[Function,Array],"onUpdate:checked":[Function,Array],checkedValue:{type:Boolean,default:void 0}},j=re("n-radio-group");function Ce(e){const o=ne(j,null),t=U(e,{mergedSize(r){const{size:l}=e;if(l!==void 0)return l;if(o){const{mergedSizeRef:{value:h}}=o;if(h!==void 0)return h}return r?r.mergedSize.value:"medium"},mergedDisabled(r){return!!(e.disabled||o!=null&&o.disabledRef.value||r!=null&&r.disabled.value)}}),{mergedSizeRef:a,mergedDisabledRef:n}=t,d=k(null),i=k(null),s=k(e.defaultChecked),c=I(e,"checked"),g=P(c,s),v=V(()=>o?o.valueRef.value===e.value:g.value),m=V(()=>{const{name:r}=e;if(r!==void 0)return r;if(o)return o.nameRef.value}),b=k(!1);function x(){if(o){const{doUpdateValue:r}=o,{value:l}=e;w(r,l)}else{const{onUpdateChecked:r,"onUpdate:checked":l}=e,{nTriggerFormInput:h,nTriggerFormChange:u}=t;r&&w(r,!0),l&&w(l,!0),h(),u(),s.value=!0}}function p(){n.value||v.value||x()}function C(){p(),d.value&&(d.value.checked=v.value)}function y(){b.value=!1}function z(){b.value=!0}return{mergedClsPrefix:o?o.mergedClsPrefixRef:A(e).mergedClsPrefixRef,inputRef:d,labelRef:i,mergedName:m,mergedDisabled:n,renderSafeChecked:v,focus:b,mergedSize:a,handleRadioInputChange:C,handleRadioInputBlur:y,handleRadioInputFocus:z}}const he=F("radio-group",`
 display: inline-block;
 font-size: var(--n-font-size);
`,[R("splitor",`
 display: inline-block;
 vertical-align: bottom;
 width: 1px;
 transition:
 background-color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 background: var(--n-button-border-color);
 `,[S("checked",{backgroundColor:"var(--n-button-border-color-active)"}),S("disabled",{opacity:"var(--n-opacity-disabled)"})]),S("button-group",`
 white-space: nowrap;
 height: var(--n-height);
 line-height: var(--n-height);
 `,[F("radio-button",{height:"var(--n-height)",lineHeight:"var(--n-height)"}),R("splitor",{height:"var(--n-height)"})]),F("radio-button",`
 vertical-align: bottom;
 outline: none;
 position: relative;
 user-select: none;
 -webkit-user-select: none;
 display: inline-block;
 box-sizing: border-box;
 padding-left: 14px;
 padding-right: 14px;
 white-space: nowrap;
 transition:
 background-color .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 background: var(--n-button-color);
 color: var(--n-button-text-color);
 border-top: 1px solid var(--n-button-border-color);
 border-bottom: 1px solid var(--n-button-border-color);
 `,[F("radio-input",`
 pointer-events: none;
 position: absolute;
 border: 0;
 border-radius: inherit;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 opacity: 0;
 z-index: 1;
 `),R("state-border",`
 z-index: 1;
 pointer-events: none;
 position: absolute;
 box-shadow: var(--n-button-box-shadow);
 transition: box-shadow .3s var(--n-bezier);
 left: -1px;
 bottom: -1px;
 right: -1px;
 top: -1px;
 `),_("&:first-child",`
 border-top-left-radius: var(--n-button-border-radius);
 border-bottom-left-radius: var(--n-button-border-radius);
 border-left: 1px solid var(--n-button-border-color);
 `,[R("state-border",`
 border-top-left-radius: var(--n-button-border-radius);
 border-bottom-left-radius: var(--n-button-border-radius);
 `)]),_("&:last-child",`
 border-top-right-radius: var(--n-button-border-radius);
 border-bottom-right-radius: var(--n-button-border-radius);
 border-right: 1px solid var(--n-button-border-color);
 `,[R("state-border",`
 border-top-right-radius: var(--n-button-border-radius);
 border-bottom-right-radius: var(--n-button-border-radius);
 `)]),$("disabled",`
 cursor: pointer;
 `,[_("&:hover",[R("state-border",`
 transition: box-shadow .3s var(--n-bezier);
 box-shadow: var(--n-button-box-shadow-hover);
 `),$("checked",{color:"var(--n-button-text-color-hover)"})]),S("focus",[_("&:not(:active)",[R("state-border",{boxShadow:"var(--n-button-box-shadow-focus)"})])])]),S("checked",`
 background: var(--n-button-color-active);
 color: var(--n-button-text-color-active);
 border-color: var(--n-button-border-color-active);
 `),S("disabled",`
 cursor: not-allowed;
 opacity: var(--n-opacity-disabled);
 `)])]);function ve(e,o,t){var a;const n=[];let d=!1;for(let i=0;i<e.length;++i){const s=e[i],c=(a=s.type)===null||a===void 0?void 0:a.name;c==="RadioButton"&&(d=!0);const g=s.props;if(c!=="RadioButton"){n.push(s);continue}if(i===0)n.push(s);else{const v=n[n.length-1].props,m=o===v.value,b=v.disabled,x=o===g.value,p=g.disabled,C=(m?2:0)+(b?0:1),y=(x?2:0)+(p?0:1),z={[`${t}-radio-group__splitor--disabled`]:b,[`${t}-radio-group__splitor--checked`]:m},r={[`${t}-radio-group__splitor--disabled`]:p,[`${t}-radio-group__splitor--checked`]:x},l=C<y?r:z;n.push(E("div",{class:[`${t}-radio-group__splitor`,l]}),s)}}return{children:n,isButtonGroup:d}}const fe=Object.assign(Object.assign({},M.props),{name:String,value:[String,Number,Boolean],defaultValue:{type:[String,Number,Boolean],default:null},size:String,disabled:{type:Boolean,default:void 0},"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array]}),Re=ae({name:"RadioGroup",props:fe,setup(e){const o=k(null),{mergedSizeRef:t,mergedDisabledRef:a,nTriggerFormChange:n,nTriggerFormInput:d,nTriggerFormBlur:i,nTriggerFormFocus:s}=U(e),{mergedClsPrefixRef:c,inlineThemeDisabled:g,mergedRtlRef:v}=A(e),m=M("Radio","-radio-group",he,be,e,c),b=k(e.defaultValue),x=I(e,"value"),p=P(x,b);function C(u){const{onUpdateValue:f,"onUpdate:value":B}=e;f&&w(f,u),B&&w(B,u),b.value=u,n(),d()}function y(u){const{value:f}=o;f&&(f.contains(u.relatedTarget)||s())}function z(u){const{value:f}=o;f&&(f.contains(u.relatedTarget)||i())}de(j,{mergedClsPrefixRef:c,nameRef:I(e,"name"),valueRef:p,disabledRef:a,mergedSizeRef:t,doUpdateValue:C});const r=se("Radio",v,c),l=D(()=>{const{value:u}=t,{common:{cubicBezierEaseInOut:f},self:{buttonBorderColor:B,buttonBorderColorActive:G,buttonBorderRadius:L,buttonBoxShadow:O,buttonBoxShadowFocus:K,buttonBoxShadowHover:N,buttonColor:Y,buttonColorActive:Z,buttonTextColor:q,buttonTextColorActive:J,buttonTextColorHover:Q,opacityDisabled:W,[H("buttonHeight",u)]:X,[H("fontSize",u)]:ee}}=m.value;return{"--n-font-size":ee,"--n-bezier":f,"--n-button-border-color":B,"--n-button-border-color-active":G,"--n-button-border-radius":L,"--n-button-box-shadow":O,"--n-button-box-shadow-focus":K,"--n-button-box-shadow-hover":N,"--n-button-color":Y,"--n-button-color-active":Z,"--n-button-text-color":q,"--n-button-text-color-hover":Q,"--n-button-text-color-active":J,"--n-height":X,"--n-opacity-disabled":W}}),h=g?le("radio-group",D(()=>t.value[0]),l,e):void 0;return{selfElRef:o,rtlEnabled:r,mergedClsPrefix:c,mergedValue:p,handleFocusout:z,handleFocusin:y,cssVars:g?void 0:l,themeClass:h==null?void 0:h.themeClass,onRender:h==null?void 0:h.onRender}},render(){var e;const{mergedValue:o,mergedClsPrefix:t,handleFocusin:a,handleFocusout:n}=this,{children:d,isButtonGroup:i}=ve(ie(ue(this)),o,t);return(e=this.onRender)===null||e===void 0||e.call(this),E("div",{onFocusin:a,onFocusout:n,ref:"selfElRef",class:[`${t}-radio-group`,this.rtlEnabled&&`${t}-radio-group--rtl`,this.themeClass,i&&`${t}-radio-group--button-group`],style:this.cssVars},d)}});export{Re as _,be as a,xe as r,Ce as s};
