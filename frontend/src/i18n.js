import { ref, computed, watchEffect } from 'vue'

const STORAGE_KEY = 'garupa-locale'
const SUPPORTED_LOCALES = ['zh', 'ja', 'en']

export const LOCALE_OPTIONS = [
  { value: 'zh', label: '简体中文', short: '简中' },
  { value: 'ja', label: '日本語', short: '日本語' },
  { value: 'en', label: 'English', short: 'EN' },
]

function getInitialLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (SUPPORTED_LOCALES.includes(saved)) {
      return saved
    }
  } catch (_) {
    // ignore storage errors
  }

  if (typeof navigator !== 'undefined' && navigator.language) {
    const lang = navigator.language.toLowerCase()
    if (lang.startsWith('ja')) return 'ja'
    if (lang.startsWith('en')) return 'en'
  }
  return 'zh'
}

export const locale = ref(getInitialLocale())

export const dateLocaleTag = computed(() => {
  if (locale.value === 'ja') return 'ja-JP'
  if (locale.value === 'en') return 'en-US'
  return 'zh-CN'
})

const messages = {
  zh: {
    'app.title': '日服 T10 追踪',
    'app.toggleNav': '切换导航',
    'nav.events': '活动',
    'nav.monthly': '月榜',
    'nav.playerSearch': '玩家查询',
    'mode.event': '活动榜',
    'mode.monthly': '月榜',
    'theme.dark': '夜间模式',
    'theme.light': '日间模式',
    'theme.systemSuffix': '（跟随系统）',
    'theme.toggleTitle': '当前：{current}{suffix}，点击切换至{next}',
    'lang.switchLabel': '切换语言',

    'common.selectPlaceholder': '请选择',
    'common.loading': '加载中...',
    'common.refreshing': '刷新中...',
    'common.chartLoading': '图表加载中...',
    'common.refreshCountdown': '刷新 ({sec}s)',
    'common.start': '开始: ',
    'common.end': '结束: ',
    'common.upcomingChip': '未开始',
    'common.builtByPrefix': '由 ',
    'common.builtBySuffix': ' 构建 / ',

    'table.updatedAt': '当前更新时间：{time}',
    'table.rank': '位次',
    'table.uid': 'UID',
    'table.name': '名字',
    'table.pt': '当前PT',
    'table.gap': '当前分差',
    'table.hourlySpeed': '上一整点时速',
    'table.speedRank': '时速排名',
    'table.runCount': '周回次数',
    'table.avgPt': '平均PT',
    'table.signature': '签名',
    'table.noHeatmap': '暂无热力图数据',

    'songTable.score': '最高分',
    'songTable.scoreGap': '分差',
    'songTable.noData': '暂无歌榜数据',
    'songTable.medleyAggregate': '组曲总分榜',
    'songTable.songLabel': '曲目 #{id}',

    'heatmap.now': '现在',
    'heatmap.ago48h': '48h前',
    'heatmap.cellTooltip': '{label} ·  {count} 次',
    'heatmap.cellTooltipOne': '{label} ·  {count} 次',

    'event.selectPlaceholder': '选择活动',
    'event.bestdoriPrefix': '感谢',
    'event.bestdoriSuffix': '提供数据',
    'event.t10SpeedTitle': 'T10 时速',
    'event.songRankingTitle': '歌榜 T10',
    'event.tabPtRanking': '活动PT榜 (肝榜)',
    'event.tabSongRanking': '歌榜',
    'event.selectSongPlaceholder': '选择曲目',
    'event.speedCurveTitle': '时速曲线',
    'event.upcomingTitle': '活动暂未开始',
    'event.upcomingSubtitle': '距离活动开始还有',
    'event.type.live_try': 'Live 试炼',
    'event.type.challenge': '挑战 Live',
    'event.type.mission_live': '任务 Live',
    'event.type.versus': '竞演 Live',
    'event.type.medley': '组曲',
    'event.type.festival': '5 v 5',

    'monthly.selectPlaceholder': '选择月榜',
    'monthly.titleFallback': '月榜',
    'monthly.chip': '月榜',
    'monthly.t10SpeedTitle': '月榜 T10 时速',
    'monthly.ptCurveTitle': '月榜 PT 曲线',
    'monthly.upcomingTitle': '本月榜暂未开始',
    'monthly.upcomingSubtitle': '距离开始还有',

    'chart.hideAll': '隐藏所有',
    'chart.showAll': '显示所有',

    'player.title': '玩家查询',
    'player.inputPlaceholder': '输入玩家 UID',
    'player.searchBtn': '查询',
    'player.privateId': 'ID未公开',
    'player.rank': '等级 {rank}',
    'player.nameHistory': '曾用名',
    'player.viewNameHistory': '查看曾用名',
    'player.closeNameHistory': '关闭曾用名',
    'player.noNameHistory': '暂无用户名记录。',
    'player.t10Records': 'T10 记录',
    'player.songRankingRecords': '歌榜 T10 记录',
    'player.songT1Badge': 'T1 × {count}',
    'player.eventNum': '活动 #{id}',
    'player.rankPlace': '{rank} 位',
    'player.noT10Records': '该玩家暂无 T10 记录。',
    'player.noSongT10Records': '该玩家暂无歌榜 T10 记录。',
    'player.mainBand': '主乐队',
    'player.bandPower': '综合力',
    'player.bandRank': '乐队等级',
    'player.charRank': '角色等级',
    'player.areaItems': '基建等级',
    'player.notFound': '未能找到玩家',
    'player.emptyPrompt': '请输入玩家 UID 以查询玩家信息和 T10 记录。',
    'player.localOnlyNotice': '该玩家当前名片未公开或暂无法从服务器拉取，以下展示本地归档的 T10 战绩记录。',
    'player.leadBy': '领先第2名 +{pt}',
    'player.gapToFirst': '距第1名 -{pt}',
    'player.gapToPrev': '距前1名 -{pt}',
    'player.nameUsedAtEvent': '当时昵称：{name}',
    'player.expandDetail': '展开曲线',
    'player.collapseDetail': '收起曲线',
    'player.compareCheckbox': '对比曲线',
    'player.compareTitle': '多期活动 PT 曲线对比',
    'player.compareHint': '可再勾选其他带曲线的活动，按开服起经过小时数同屏对齐对比',
    'player.compareClear': '清空对比',
    'player.compareHoursLabel': '开服后小时 (h)',
    'player.showRefs': '显示 T1 / T10 参考线',
    'player.refTop1': 'T1',
    'player.refTop10': 'T10',
    'player.detailLoading': '正在加载曲线...',
    'player.noCurveData': '该期暂无个人曲线数据',
    'player.viewEventPage': '查看活动页',
    'player.eventTrends': '活动 PT 曲线',
    'player.monthlyTrends': '月榜 PT 曲线',
    'player.monthlyNum': '月榜 #{id}',
    'player.viewMonthlyPage': '查看月榜页',

    'notFound.title': '页面不存在',
    'notFound.description': '你要访问的活动不存在，可能已被删除，或链接有误',
    'notFound.backHome': '返回首页',
  },
  ja: {
    'app.title': 'ガルパ T10 トラッカー',
    'app.toggleNav': 'メニューを切り替え',
    'nav.events': 'イベント',
    'nav.monthly': 'マンスリー',
    'nav.playerSearch': 'プレイヤー検索',
    'mode.event': 'イベント',
    'mode.monthly': 'マンスリー',
    'theme.dark': 'ダークモード',
    'theme.light': 'ライトモード',
    'theme.systemSuffix': '（システム設定）',
    'theme.toggleTitle': '現在：{current}{suffix}（クリックで{next}に切替）',
    'lang.switchLabel': '言語を切り替え',

    'common.selectPlaceholder': '選択してください',
    'common.loading': '読み込み中...',
    'common.refreshing': '更新中...',
    'common.chartLoading': 'グラフ読込中...',
    'common.refreshCountdown': '更新 ({sec}s)',
    'common.start': '開始: ',
    'common.end': '終了: ',
    'common.upcomingChip': '開催前',
    'common.builtByPrefix': 'Built with ',
    'common.builtBySuffix': ' / ',

    'table.updatedAt': '最終更新：{time}',
    'table.rank': '順位',
    'table.uid': 'UID',
    'table.name': '名前',
    'table.pt': '現在PT',
    'table.gap': '直上差',
    'table.hourlySpeed': '前時間時速',
    'table.speedRank': '時速順位',
    'table.runCount': '周回数',
    'table.avgPt': '平均PT',
    'table.signature': 'コメント',
    'table.noHeatmap': 'ヒートマップデータなし',

    'songTable.score': 'ハイスコア',
    'songTable.scoreGap': '上位差',
    'songTable.noData': '楽曲ランキングデータがありません',
    'songTable.medleyAggregate': 'メドレー合計スコア',
    'songTable.songLabel': '楽曲 #{id}',

    'heatmap.now': '現在',
    'heatmap.ago48h': '48h前',
    'heatmap.cellTooltip': '{label} · {count} 周',
    'heatmap.cellTooltipOne': '{label} · {count} 周',

    'event.selectPlaceholder': 'イベントを選択',
    'event.bestdoriPrefix': 'データ提供:',
    'event.bestdoriSuffix': '',
    'event.t10SpeedTitle': 'T10 時速',
    'event.songRankingTitle': '楽曲ランキング T10',
    'event.tabPtRanking': 'イベントP (肝榜)',
    'event.tabSongRanking': '楽曲 (歌榜)',
    'event.selectSongPlaceholder': '楽曲を選択',
    'event.speedCurveTitle': 'PT推移グラフ',
    'event.upcomingTitle': 'イベント開催前',
    'event.upcomingSubtitle': '開始まであと',
    'event.type.live_try': 'ライブトライ！',
    'event.type.challenge': 'チャレンジライブ',
    'event.type.mission_live': 'ミッションライブ',
    'event.type.versus': '対バンライブ',
    'event.type.medley': 'メドレーライブ',
    'event.type.festival': 'チームライブフェス',

    'monthly.selectPlaceholder': '月間ランキングを選択',
    'monthly.titleFallback': '月間ランキング',
    'monthly.chip': '月間ランキング',
    'monthly.t10SpeedTitle': '月間 T10 時速',
    'monthly.ptCurveTitle': '月間 PT 推移',
    'monthly.upcomingTitle': '今月のランキングは開催前です',
    'monthly.upcomingSubtitle': '開始まであと',

    'chart.hideAll': 'すべて非表示',
    'chart.showAll': 'すべて表示',

    'player.title': 'プレイヤー検索',
    'player.inputPlaceholder': 'プレイヤーUIDを入力',
    'player.searchBtn': '検索',
    'player.privateId': 'ID非公開',
    'player.rank': 'ランク {rank}',
    'player.nameHistory': '過去の名前',
    'player.viewNameHistory': '過去の名前を表示',
    'player.closeNameHistory': '閉じる',
    'player.noNameHistory': '名前の履歴はありません。',
    'player.t10Records': 'TOP10 記録',
    'player.songRankingRecords': '楽曲ランキング TOP10 記録',
    'player.songT1Badge': '1位 × {count}',
    'player.eventNum': 'イベント #{id}',
    'player.rankPlace': '{rank} 位',
    'player.noT10Records': 'TOP10の記録はありません。',
    'player.noSongT10Records': '楽曲ランキングのTOP10記録はありません。',
    'player.mainBand': 'メインバンド',
    'player.bandPower': 'バンド総合力',
    'player.bandRank': 'バンドランク',
    'player.charRank': 'キャラランク',
    'player.areaItems': 'エリアアイテム',
    'player.notFound': 'プレイヤーが見つかりません',
    'player.emptyPrompt': 'プレイヤーUIDを入力して、プロフィールやTOP10記録を検索できます。',
    'player.localOnlyNotice': '現在プロフィールが非公開または取得できないため、ローカルに保存されている TOP10 戦績のみ表示しています。',
    'player.leadBy': '2位差 +{pt}',
    'player.gapToFirst': '1位差 -{pt}',
    'player.gapToPrev': '上位差 -{pt}',
    'player.nameUsedAtEvent': '当時の名前：{name}',
    'player.expandDetail': 'グラフを表示',
    'player.collapseDetail': 'グラフを閉じる',
    'player.compareCheckbox': 'グラフ比較',
    'player.compareTitle': '複数イベント PT グラフ比較',
    'player.compareHint': '別のイベントもチェックすると、開催経過時間（h）で重ねて比較できます',
    'player.compareClear': '選択解除',
    'player.compareHoursLabel': '経過時間 (h)',
    'player.showRefs': 'T1 / T10 の参考ラインを表示',
    'player.refTop1': 'T1',
    'player.refTop10': 'T10',
    'player.detailLoading': 'グラフ読込中...',
    'player.noCurveData': 'このイベントの個人推移データはありません',
    'player.viewEventPage': 'イベント詳細へ',
    'player.eventTrends': 'イベント PT グラフ',
    'player.monthlyTrends': '月間 PT グラフ',
    'player.monthlyNum': '月間 #{id}',
    'player.viewMonthlyPage': '月間ページへ',

    'notFound.title': 'ページが見つかりません',
    'notFound.description': 'お探しのイベントは存在しないか、削除されたか、URLが間違っている可能性があります',
    'notFound.backHome': 'ホームに戻る',
  },
  en: {
    'app.title': 'Garupa JP T10 Tracker',
    'app.toggleNav': 'Toggle navigation',
    'nav.events': 'Events',
    'nav.monthly': 'Monthly',
    'nav.playerSearch': 'Player Search',
    'mode.event': 'Event',
    'mode.monthly': 'Monthly',
    'theme.dark': 'Dark mode',
    'theme.light': 'Light mode',
    'theme.systemSuffix': ' (System)',
    'theme.toggleTitle': 'Current: {current}{suffix}. Click to switch to {next}',
    'lang.switchLabel': 'Switch language',

    'common.selectPlaceholder': 'Select...',
    'common.loading': 'Loading...',
    'common.refreshing': 'Refreshing...',
    'common.chartLoading': 'Loading chart...',
    'common.refreshCountdown': 'Refresh ({sec}s)',
    'common.start': 'Start: ',
    'common.end': 'End: ',
    'common.upcomingChip': 'Upcoming',
    'common.builtByPrefix': 'Built with ',
    'common.builtBySuffix': ' / ',

    'table.updatedAt': 'Last updated: {time}',
    'table.rank': 'Rank',
    'table.uid': 'UID',
    'table.name': 'Name',
    'table.pt': 'Current PT',
    'table.gap': 'Gap',
    'table.hourlySpeed': 'Hourly Speed',
    'table.speedRank': 'Speed Rank',
    'table.runCount': 'Games',
    'table.avgPt': 'Avg PT',
    'table.signature': 'Comment',
    'table.noHeatmap': 'No heatmap data',

    'songTable.score': 'High Score',
    'songTable.scoreGap': 'Gap',
    'songTable.noData': 'No song ranking data available',
    'songTable.medleyAggregate': 'Medley Aggregate Score',
    'songTable.songLabel': 'Song #{id}',

    'heatmap.now': 'Now',
    'heatmap.ago48h': '48h ago',
    'heatmap.cellTooltip': '{label} · {count} games',
    'heatmap.cellTooltipOne': '{label} · {count} game',

    'event.selectPlaceholder': 'Select Event',
    'event.bestdoriPrefix': 'Data provided by',
    'event.bestdoriSuffix': '',
    'event.t10SpeedTitle': 'T10 Pacing',
    'event.songRankingTitle': 'Song Ranking T10',
    'event.tabPtRanking': 'Event PT',
    'event.tabSongRanking': 'Song Ranking',
    'event.selectSongPlaceholder': 'Select Song',
    'event.speedCurveTitle': 'PT Progression',
    'event.upcomingTitle': 'Event Not Started Yet',
    'event.upcomingSubtitle': 'Starts in',
    'event.type.live_try': 'Live Goals',
    'event.type.challenge': 'Challenge Live',
    'event.type.mission_live': 'Mission Live',
    'event.type.versus': 'VS Live',
    'event.type.medley': 'Medley Live',
    'event.type.festival': 'Team Live Festival',

    'monthly.selectPlaceholder': 'Select Monthly Ranking',
    'monthly.titleFallback': 'Monthly Ranking',
    'monthly.chip': 'Monthly Ranking',
    'monthly.t10SpeedTitle': 'Monthly T10 Pacing',
    'monthly.ptCurveTitle': 'Monthly PT Progression',
    'monthly.upcomingTitle': 'Monthly Ranking Not Started Yet',
    'monthly.upcomingSubtitle': 'Starts in',

    'chart.hideAll': 'Hide All',
    'chart.showAll': 'Show All',

    'player.title': 'Player Search',
    'player.inputPlaceholder': 'Enter Player UID',
    'player.searchBtn': 'Search',
    'player.privateId': 'Private ID',
    'player.rank': 'Rank {rank}',
    'player.nameHistory': 'Name History',
    'player.viewNameHistory': 'View name history',
    'player.closeNameHistory': 'Close name history',
    'player.noNameHistory': 'No name history found.',
    'player.t10Records': 'T10 Records',
    'player.songRankingRecords': 'Song Ranking T10 Records',
    'player.songT1Badge': '#1 × {count}',
    'player.eventNum': 'Event #{id}',
    'player.rankPlace': '#{rank}',
    'player.noT10Records': 'No T10 records found for this player.',
    'player.noSongT10Records': 'No Song Ranking T10 records found for this player.',
    'player.mainBand': 'Main Band',
    'player.bandPower': 'Band Power',
    'player.bandRank': 'Band Rank',
    'player.charRank': 'Character Rank',
    'player.areaItems': 'Area Items',
    'player.notFound': 'Player Not Found',
    'player.emptyPrompt': 'Enter a player UID to look up their profile and T10 records.',
    'player.localOnlyNotice': 'Live profile is private or unavailable; showing locally archived T10 career records below.',
    'player.leadBy': 'Lead +{pt}',
    'player.gapToFirst': '1st Gap -{pt}',
    'player.gapToPrev': 'Prev Gap -{pt}',
    'player.nameUsedAtEvent': 'Used name: {name}',
    'player.expandDetail': 'Show PT Curve',
    'player.collapseDetail': 'Hide Curve',
    'player.compareCheckbox': 'Compare',
    'player.compareTitle': 'Multi-Event PT Curve Comparison',
    'player.compareHint': 'Select another event with curve data to overlay elapsed pacing (hours since start)',
    'player.compareClear': 'Clear',
    'player.compareHoursLabel': 'Hours Since Start (h)',
    'player.showRefs': 'Show T1 / T10 reference lines',
    'player.refTop1': 'T1',
    'player.refTop10': 'T10',
    'player.detailLoading': 'Loading PT curve...',
    'player.noCurveData': 'No curve data recorded for this period',
    'player.viewEventPage': 'Open Event',
    'player.eventTrends': 'Event PT Curves',
    'player.monthlyTrends': 'Monthly PT Curves',
    'player.monthlyNum': 'Monthly #{id}',
    'player.viewMonthlyPage': 'Open Monthly',

    'notFound.title': 'Page Not Found',
    'notFound.description': 'The event you are looking for does not exist, may have been removed, or the URL is incorrect.',
    'notFound.backHome': 'Back to Home',
  },
}

export function t(key, params = {}) {
  const dict = messages[locale.value] || messages.zh
  let str = dict[key] ?? messages.zh[key] ?? key
  for (const [k, v] of Object.entries(params)) {
    str = str.replaceAll(`{${k}}`, String(v))
  }
  return str
}

export function formatCountdown(ms) {
  const pad = n => String(n).padStart(2, '0')
  const safeMs = Math.max(0, ms)
  const totalSec = Math.floor(safeMs / 1000)
  const d = Math.floor(totalSec / 86400)
  const h = Math.floor((totalSec % 86400) / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60

  if (locale.value === 'ja') {
    return `${pad(d)} 日 ${pad(h)} 時間 ${pad(m)} 分 ${pad(s)} 秒`
  }
  if (locale.value === 'en') {
    return `${pad(d)}d ${pad(h)}h ${pad(m)}m ${pad(s)}s`
  }
  return `${pad(d)} 日 ${pad(h)} 时 ${pad(m)} 分 ${pad(s)} 秒`
}

function syncDocumentMeta() {
  if (typeof document === 'undefined') return
  document.documentElement.lang = dateLocaleTag.value
}

export function setLocale(newLocale) {
  if (!SUPPORTED_LOCALES.includes(newLocale)) return
  locale.value = newLocale
  try {
    localStorage.setItem(STORAGE_KEY, newLocale)
  } catch (_) {
    // ignore storage errors
  }
  syncDocumentMeta()
}

watchEffect(() => {
  syncDocumentMeta()
})

export function useI18n() {
  return {
    locale,
    LOCALE_OPTIONS,
    setLocale,
    dateLocaleTag,
    t,
    formatCountdown,
  }
}
