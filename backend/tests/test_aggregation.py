import unittest
from src.services.aggregation import (parse_ts,week_of,week_label,weeks_spanned,parse_week,
 merge,intersect,night_windows,duration,aggregate_week)
def ev(start,end,article='A',ratio=0.5,state='active',event_id='E',revoke_reason=''):
 return {'start':parse_ts(start),'end':parse_ts(end),'article':article,'ratio':ratio,
 'state':state,'event_id':event_id,'revoke_reason':revoke_reason}
W1=parse_week('2026-11-09')  # 北京时间周一
W2=parse_week('2026-11-16')
class WeekTest(unittest.TestCase):
 def test_week_of_beijing_boundary(self):
  # UTC周日16:00即北京周一00:00，属于新的一周
  self.assertEqual(week_label(week_of(parse_ts('2026-11-08T16:00:00Z'))),'2026-11-09')
  self.assertEqual(week_label(week_of(parse_ts('2026-11-08T15:59:59Z'))),'2026-11-02')
 def test_parse_week_requires_monday(self):
  with self.assertRaises(ValueError):parse_week('2026-11-10')
 def test_naive_treated_as_beijing(self):
  self.assertEqual(parse_ts('2026-11-10T22:30').utcoffset().total_seconds(),8*3600)
 def test_weeks_spanned_cross_week(self):
  spans=weeks_spanned(parse_ts('2026-11-15T23:30+08:00'),parse_ts('2026-11-16T00:30+08:00'))
  self.assertEqual([week_label(m) for m in spans],['2026-11-09','2026-11-16'])
 def test_weeks_spanned_same_week(self):
  spans=weeks_spanned(parse_ts('2026-11-10T08:00+08:00'),parse_ts('2026-11-10T09:00+08:00'))
  self.assertEqual([week_label(m) for m in spans],['2026-11-09'])
class MergeTest(unittest.TestCase):
 def test_nested_overlap_merges_to_union(self):
  # 嵌套重叠：内层时段不重复计时长
  merged=merge([(parse_ts('2026-11-10T10:00+08:00'),parse_ts('2026-11-10T12:00+08:00')),
   (parse_ts('2026-11-10T10:30+08:00'),parse_ts('2026-11-10T11:30+08:00')),
   (parse_ts('2026-11-10T11:00+08:00'),parse_ts('2026-11-10T13:00+08:00'))])
  self.assertEqual(duration(merged),3*3600)
  self.assertEqual(len(merged),1)
 def test_touching_intervals_merge(self):
  merged=merge([(parse_ts('2026-11-10T10:00+08:00'),parse_ts('2026-11-10T11:00+08:00')),
   (parse_ts('2026-11-10T11:00+08:00'),parse_ts('2026-11-10T12:00+08:00'))])
  self.assertEqual(duration(merged),2*3600)
 def test_disjoint_intervals_kept(self):
  merged=merge([(parse_ts('2026-11-10T10:00+08:00'),parse_ts('2026-11-10T11:00+08:00')),
   (parse_ts('2026-11-10T12:00+08:00'),parse_ts('2026-11-10T13:00+08:00'))])
  self.assertEqual(len(merged),2)
class AggregateTest(unittest.TestCase):
 def test_cross_week_clip(self):
  # 跨周事件被裁剪：周日23:30-24:00归上一周，周一00:00-00:30归下一周
  e=ev('2026-11-15T23:30+08:00','2026-11-16T00:30+08:00',ratio=0.8)
  r1=aggregate_week([e],W1);r2=aggregate_week([e],W2)
  self.assertEqual(r1['detail']['total_seconds'],1800)
  self.assertEqual(r2['detail']['total_seconds'],1800)
  self.assertEqual(r1['night_share'],1.0)  # 两段都在夜读窗口
  self.assertEqual(r2['night_share'],1.0)
  self.assertEqual(r1['weekly_reading'],1)
  self.assertEqual(r2['weekly_reading'],1)
 def test_nested_overlap_not_double_counted(self):
  # 跨设备嵌套重叠：三篇同时段文章，时段并集只有3小时
  events=[ev('2026-11-10T10:00+08:00','2026-11-10T12:00+08:00','A-1',0.4),
   ev('2026-11-10T10:30+08:00','2026-11-10T11:30+08:00','A-2',0.6),
   ev('2026-11-10T11:00+08:00','2026-11-10T13:00+08:00','A-3',0.9)]
  r=aggregate_week(events,W1)
  self.assertEqual(r['weekly_reading'],3)
  self.assertEqual(r['detail']['total_seconds'],3*3600)
  self.assertEqual(r['night_share'],0.0)  # 全部在白天，占比0而非留空
 def test_completion_max_per_article_then_mean(self):
  events=[ev('2026-11-10T10:00+08:00','2026-11-10T10:30+08:00','A-1',0.4,'active','E1'),
   ev('2026-11-10T11:00+08:00','2026-11-10T11:30+08:00','A-1',0.9,'active','E2'),
   ev('2026-11-10T12:00+08:00','2026-11-10T12:30+08:00','A-2',0.5,'active','E3')]
  r=aggregate_week(events,W1)
  self.assertEqual(r['weekly_reading'],2)  # 篇数按文章去重
  self.assertAlmostEqual(r['completion'],0.7)  # (max(0.4,0.9)+0.5)/2
 def test_night_share_uses_union(self):
  # 夜读重叠部分只计一次：并集1.5h / 全部并集2.5h
  events=[ev('2026-11-10T22:00+08:00','2026-11-10T23:00+08:00','A-1',0.5,'active','E1'),
   ev('2026-11-10T22:30+08:00','2026-11-10T23:30+08:00','A-2',0.5,'active','E2'),
   ev('2026-11-11T12:00+08:00','2026-11-11T13:00+08:00','A-3',0.5,'active','E3')]
  r=aggregate_week(events,W1)
  self.assertEqual(r['detail']['night_seconds'],5400)
  self.assertEqual(r['detail']['total_seconds'],9000)
  self.assertAlmostEqual(r['night_share'],0.6)
 def test_night_window_across_midnight(self):
  e=ev('2026-11-10T23:00+08:00','2026-11-11T01:00+08:00')
  r=aggregate_week([e],W1)
  self.assertEqual(r['night_share'],1.0)
 def test_zero_duration_left_blank(self):
  r=aggregate_week([],W1)
  self.assertEqual(r['weekly_reading'],0)
  self.assertIsNone(r['completion'])
  self.assertIsNone(r['night_share'])
 def test_all_revoked_left_blank(self):
  events=[ev('2026-11-10T22:00+08:00','2026-11-10T23:00+08:00','A-1',0.5,'revoked','E1','设备异常')]
  r=aggregate_week(events,W1)
  self.assertEqual(r['weekly_reading'],0)
  self.assertIsNone(r['night_share'])
  self.assertEqual(r['detail']['revoked_events'],1)
  self.assertEqual(r['detail']['revoked'][0]['reason'],'设备异常')
 def test_utc_event_assigned_to_beijing_week(self):
  # 2026-11-08T16:30Z = 北京周一00:30，落在11-09自然周且为夜读
  e=ev('2026-11-08T16:30:00Z','2026-11-08T17:30:00Z')
  r=aggregate_week([e],W1)
  self.assertEqual(r['weekly_reading'],1)
  self.assertEqual(r['night_share'],1.0)
  r0=aggregate_week([e],parse_week('2026-11-02'))
  self.assertEqual(r0['weekly_reading'],0)
 def test_event_outside_week_ignored(self):
  e=ev('2026-11-20T10:00+08:00','2026-11-20T11:00+08:00')
  r=aggregate_week([e],W1)
  self.assertEqual(r['weekly_reading'],0)
  self.assertEqual(r['detail']['total_seconds'],0)
if __name__=='__main__':unittest.main()
