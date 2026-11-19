# 六叔數據倉庫（liu-shu-data）

「六叔」三個版本 App 共用的公開數據源，每晚攪珠後自動更新：

- `draws.json` — 六合彩攪珠結果全歷史（02/053 起）：期號、日期、攪出號碼、特別號碼、頭獎派彩、得獎注數、金多寶名稱。來源：東網查績王公開 API 對齊馬會官方紀錄；24/115 一期東網獨缺，由 App 紀錄補回。
- `next_draw.json` — 下期攪珠預告：期數、日期、截止售票時間、估計頭獎基金。

App 讀取（CDN）：

- https://cdn.jsdelivr.net/gh/07502229d/liu-shu-data@main/draws.json
- https://cdn.jsdelivr.net/gh/07502229d/liu-shu-data@main/next_draw.json

攪珠結果等公開數據之事實本身不受版權保護；一切以香港賽馬會官方公佈為準。本倉庫與香港賽馬會絕無任何官方合作、附屬或授權關係。
