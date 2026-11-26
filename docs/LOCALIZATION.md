# Interface language

English is the source language. The optional Simplified Chinese translation is
written for blindfolded cubers; WCA abbreviations, notation and sticker IDs
remain usable across languages. Examples:

| English | 简体中文 |
| --- | --- |
| Blindfolded solving | 盲拧 |
| Letter scheme / letter pair | 编码方案 / 字母对 |
| Mnemonic word | 联想词 |
| Edge / corner | 棱块 / 角块 |
| Buffer piece / buffer sticker | 缓冲块 / 缓冲位贴纸 |
| Cycle break | 开小循环（选择小循环起点） |
| Commutator / setup moves | 交换子 / 预置步 |
| In-place corner twist / edge flip | 原地翻角 / 原地翻棱 |
| Scramble / memo / recall / execution | 打乱 / 记忆 / 回忆 / 执行 |
| Ao5 | 五次去尾平均（Ao5） |

Terminology reference: [BLDDB’s Chinese documentation](https://docs.blddb.net/zh/).

For new UI copy, wrap an authored literal or template with `tr` at the control,
or use `message` for copy shared with a later view. Add the translation to
`core/zh_cn.py`. Pass numbers, sticker IDs and any personal text as separate
arguments: never look up an arbitrary name, note or letter in the catalog.
Use stable, language-independent keys for routing, dropdowns and storage.

Only the browser’s interface-language key is written when switching languages.
Flutter’s locale, site controls and local font follow that selection without
reloading the app. The sign-in handoff remembers the choice for the redirect
in that tab. WCA’s own authorization page is managed by WCA.

The compact Chinese UI font is already built. If a translation adds characters,
rebuild it with `tools/subset_hans_font.py` (see its usage), and ship the font
and OFL notice together. User-generated text can also use system fallback fonts.
