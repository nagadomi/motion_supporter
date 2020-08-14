# -*- coding: utf-8 -*-
#
import os
import wx
import wx.lib.newevent
import sys

from form.panel.BasePanel import BasePanel
from form.parts.BaseFilePickerCtrl import BaseFilePickerCtrl
from form.parts.HistoryFilePickerCtrl import HistoryFilePickerCtrl
from form.parts.ConsoleCtrl import ConsoleCtrl
from form.worker.IKtoFKWorkerThread import IKtoFKWorkerThread
from utils import MFormUtils, MFileUtils
from utils.MLogger import MLogger # noqa

logger = MLogger(__name__)

# イベント定義
(IKtoFKThreadEvent, EVT_SMOOTH_THREAD) = wx.lib.newevent.NewEvent()


class IKtoFKPanel(BasePanel):
        
    def __init__(self, frame: wx.Frame, ik2fk: wx.Notebook, tab_idx: int):
        super().__init__(frame, ik2fk, tab_idx)
        self.convert_ik2fk_worker = None

        self.header_sizer = wx.BoxSizer(wx.VERTICAL)

        self.description_txt = wx.StaticText(self, wx.ID_ANY, u"IKを含むモーションをFK（回転のみ）に焼き込みます", wx.DefaultPosition, wx.DefaultSize, 0)
        self.header_sizer.Add(self.description_txt, 0, wx.ALL, 5)

        self.static_line01 = wx.StaticLine(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL)
        self.header_sizer.Add(self.static_line01, 0, wx.EXPAND | wx.ALL, 5)

        # 対象VMDファイルコントロール
        self.ik2fk_vmd_file_ctrl = HistoryFilePickerCtrl(self.frame, self, u"対象モーションVMD", u"対象モーションVMDファイルを開く", ("vmd"), wx.FLP_DEFAULT_STYLE, \
                                                         u"調整したい対象モーションのVMDパスを指定してください。\nD&Dでの指定、開くボタンからの指定、履歴からの選択ができます。", \
                                                         file_model_spacer=0, title_parts_ctrl=None, title_parts2_ctrl=None, file_histories_key="ik2fk_vmd", is_change_output=True, \
                                                         is_aster=False, is_save=False, set_no=1)
        self.header_sizer.Add(self.ik2fk_vmd_file_ctrl.sizer, 1, wx.EXPAND, 0)

        # 対象PMXファイルコントロール
        self.ik2fk_model_file_ctrl = HistoryFilePickerCtrl(self.frame, self, u"適用モデルPMX", u"適用モデルPMXファイルを開く", ("pmx"), wx.FLP_DEFAULT_STYLE, \
                                                           u"モーションを適用したいモデルのPMXパスを指定してください。\n人体モデル以外にも適用可能です。\nD&Dでの指定、開くボタンからの指定、履歴からの選択ができます。", \
                                                           file_model_spacer=0, title_parts_ctrl=None, title_parts2_ctrl=None, file_histories_key="ik2fk_pmx", \
                                                           is_change_output=True, is_aster=False, is_save=False, set_no=1)
        self.header_sizer.Add(self.ik2fk_model_file_ctrl.sizer, 1, wx.EXPAND, 0)

        # 出力先VMDファイルコントロール
        self.output_ik2fk_vmd_file_ctrl = BaseFilePickerCtrl(frame, self, u"出力対象VMD", u"出力対象VMDファイルを開く", ("vmd"), wx.FLP_OVERWRITE_PROMPT | wx.FLP_SAVE | wx.FLP_USE_TEXTCTRL, \
                                                             u"調整結果の対象VMD出力パスを指定してください。\n対象VMDファイル名に基づいて自動生成されますが、任意のパスに変更することも可能です。", \
                                                             is_aster=False, is_save=True, set_no=1)
        self.header_sizer.Add(self.output_ik2fk_vmd_file_ctrl.sizer, 1, wx.EXPAND, 0)

        self.sizer.Add(self.header_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 実行ボタン
        self.ik2fk_btn_ctrl = wx.Button(self, wx.ID_ANY, u"IKtoFK", wx.DefaultPosition, wx.Size(200, 50), 0)
        self.ik2fk_btn_ctrl.SetToolTip(u"IKをFKに焼き込みます")
        self.ik2fk_btn_ctrl.Bind(wx.EVT_BUTTON, self.on_convert_ik2fk)
        btn_sizer.Add(self.ik2fk_btn_ctrl, 0, wx.ALL, 5)

        self.sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.SHAPED, 5)

        # コンソール
        self.console_ctrl = ConsoleCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size(-1, 420), \
                                        wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE | wx.HSCROLL | wx.VSCROLL | wx.WANTS_CHARS)
        self.console_ctrl.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT))
        self.console_ctrl.Bind(wx.EVT_CHAR, lambda event: MFormUtils.on_select_all(event, self.console_ctrl))
        self.sizer.Add(self.console_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        # ゲージ
        self.gauge_ctrl = wx.Gauge(self, wx.ID_ANY, 100, wx.DefaultPosition, wx.DefaultSize, wx.GA_HORIZONTAL)
        self.gauge_ctrl.SetValue(0)
        self.sizer.Add(self.gauge_ctrl, 0, wx.ALL | wx.EXPAND, 5)

        self.Layout()
        self.fit()

        # フレームに変換完了処理バインド
        self.frame.Bind(EVT_SMOOTH_THREAD, self.on_convert_ik2fk_result)

    def on_wheel_spin_ctrl(self, event: wx.Event, inc=1):
        self.frame.on_wheel_spin_ctrl(event, inc)
        self.set_output_vmd_path(event)

    # ファイル変更時の処理
    def on_change_file(self, event: wx.Event):
        self.set_output_vmd_path(event)
    
    def set_output_vmd_path(self, event, is_force=False):
        output_ik2fk_vmd_path = MFileUtils.get_output_ik2fk_vmd_path(
            self.ik2fk_vmd_file_ctrl.file_ctrl.GetPath(),
            self.ik2fk_model_file_ctrl.file_ctrl.GetPath(),
            self.output_ik2fk_vmd_file_ctrl.file_ctrl.GetPath(), is_force)

        self.output_ik2fk_vmd_file_ctrl.file_ctrl.SetPath(output_ik2fk_vmd_path)

        if len(output_ik2fk_vmd_path) >= 255 and os.name == "nt":
            logger.error("生成予定のファイルパスがWindowsの制限を超えています。\n生成予定パス: {0}".format(output_ik2fk_vmd_path), decoration=MLogger.DECORATION_BOX)
        
    # フォーム無効化
    def disable(self):
        self.ik2fk_vmd_file_ctrl.disable()
        self.ik2fk_model_file_ctrl.disable()
        self.output_ik2fk_vmd_file_ctrl.disable()
        self.ik2fk_btn_ctrl.Disable()

    # フォーム無効化
    def enable(self):
        self.ik2fk_vmd_file_ctrl.enable()
        self.ik2fk_model_file_ctrl.enable()
        self.output_ik2fk_vmd_file_ctrl.enable()
        self.ik2fk_btn_ctrl.Enable()

    # 多段分割変換
    def on_convert_ik2fk(self, event: wx.Event):
        # フォーム無効化
        self.disable()
        # タブ固定
        self.fix_tab()
        # コンソールクリア
        self.console_ctrl.Clear()
        # 出力先を多段分割パネルのコンソールに変更
        sys.stdout = self.console_ctrl

        wx.GetApp().Yield()

        self.ik2fk_vmd_file_ctrl.save()
        self.ik2fk_model_file_ctrl.save()

        # JSON出力
        MFileUtils.save_history(self.frame.mydir_path, self.frame.file_hitories)

        self.elapsed_time = 0
        result = True
        result = self.ik2fk_vmd_file_ctrl.is_valid() and self.ik2fk_model_file_ctrl.is_valid() and result

        if not result:
            # 終了音
            self.frame.sound_finish()
            # タブ移動可
            self.release_tab()
            # フォーム有効化
            self.enable()

            return result

        # 多段分割変換開始
        if self.convert_ik2fk_worker:
            logger.error("まだ処理が実行中です。終了してから再度実行してください。", decoration=MLogger.DECORATION_BOX)
        else:
            # 別スレッドで実行
            self.convert_ik2fk_worker = IKtoFKWorkerThread(self.frame, IKtoFKThreadEvent, self.frame.is_out_log, self.frame.is_saving)
            self.convert_ik2fk_worker.start()

        return result

    # 多段分割変換完了処理
    def on_convert_ik2fk_result(self, event: wx.Event):
        self.elapsed_time = event.elapsed_time
        logger.info("\n処理時間: %s", self.show_worked_time())

        # 終了音
        self.frame.sound_finish()

        # タブ移動可
        self.release_tab()
        # フォーム有効化
        self.enable()
        # ワーカー終了
        self.convert_ik2fk_worker = None
        # プログレス非表示
        self.gauge_ctrl.SetValue(0)

    def show_worked_time(self):
        # 経過秒数を時分秒に変換
        td_m, td_s = divmod(self.elapsed_time, 60)

        if td_m == 0:
            worked_time = "{0:02d}秒".format(int(td_s))
        else:
            worked_time = "{0:02d}分{1:02d}秒".format(int(td_m), int(td_s))

        return worked_time
