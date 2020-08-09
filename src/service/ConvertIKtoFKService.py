# -*- coding: utf-8 -*-
#
import math
import numpy as np
import logging
import os
import traceback
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from module.MOptions import MIKtoFKOptions, MOptionsDataSet
from mmd.PmxData import PmxModel, Bone # noqa
from mmd.VmdData import VmdMotion, VmdBoneFrame, VmdCameraFrame, VmdInfoIk, VmdLightFrame, VmdMorphFrame, VmdShadowFrame, VmdShowIkFrame # noqa
from mmd.VmdWriter import VmdWriter
from module.MParams import BoneLinks # noqa
from module.MMath import MRect, MVector3D, MVector4D, MQuaternion, MMatrix4x4 # noqa
from utils import MUtils, MServiceUtils, MBezierUtils # noqa
from utils.MLogger import MLogger # noqa
from utils.MException import SizingException

logger = MLogger(__name__, level=1)


class ConvertIKtoFKService():
    def __init__(self, options: MIKtoFKOptions):
        self.options = options

    def execute(self):
        logging.basicConfig(level=self.options.logging_level, format="%(message)s [%(module_name)s]")

        try:
            service_data_txt = "IK焼き込み処理実行\n------------------------\nexeバージョン: {version_name}\n".format(version_name=self.options.version_name) \

            service_data_txt = "{service_data_txt}　VMD: {vmd}\n".format(service_data_txt=service_data_txt,
                                    vmd=os.path.basename(self.options.motion.path)) # noqa
            service_data_txt = "{service_data_txt}　モデル: {model}({model_name})\n".format(service_data_txt=service_data_txt,
                                    model=os.path.basename(self.options.motion.path), model_name=self.options.model.name) # noqa

            logger.info(service_data_txt, decoration=MLogger.DECORATION_BOX)

            # 処理に成功しているか
            result = self.convert_ik2fk()

            # 最後に出力
            VmdWriter(MOptionsDataSet(self.options.motion, None, self.options.model, self.options.output_path, False, False, [], None, 0, [])).write()

            logger.info("出力終了: %s", os.path.basename(self.options.output_path), decoration=MLogger.DECORATION_BOX, title="成功")

            return result
        except SizingException as se:
            logger.error("IK焼き込み処理が処理できないデータで終了しました。\n\n%s", se.message, decoration=MLogger.DECORATION_BOX)
        except Exception:
            logger.critical("IK焼き込み処理が意図せぬエラーで終了しました。\n\n%s", traceback.format_exc(), decoration=MLogger.DECORATION_BOX)
        finally:
            logging.shutdown()

    # IK焼き込み処理実行
    def convert_ik2fk(self):
        futures = []

        with ThreadPoolExecutor(thread_name_prefix="ik2fk", max_workers=min(5, self.options.max_workers)) as executor:
            for bone in self.options.model.bones.values():
                if bone.getIkFlag() and bone.name in self.options.motion.bones and len(self.options.motion.bones[bone.name].keys()) > 0:
                    # IK系でキーフレがある場合、処理開始
                    futures.append(executor.submit(self.convert_target_ik2fk, bone))

        concurrent.futures.wait(futures, timeout=None, return_when=concurrent.futures.FIRST_EXCEPTION)

        for f in futures:
            if not f.result():
                return False

        return True

    # 1つのボーンに対するIK焼き込み処理
    def convert_target_ik2fk(self, ik_bone: Bone):
        motion = self.options.motion
        model = self.options.model
        bone_name = ik_bone.name

        # 差異の大きい箇所にキーフレ追加
        logger.info("-- IK焼き込み準備:開始【%s】", bone_name)
        fnos = motion.get_differ_fnos(0, [bone_name], limit_degrees=20, limit_length=3)

        prev_sep_fno = 0
        for fno in fnos:
            bf = motion.calc_bf(bone_name, fno)
            motion.regist_bf(bf, bone_name, fno)

            if fno // 1000 > prev_sep_fno and fnos[-1] > 0:
                logger.info("-- %sフレーム目:終了(%s％)【キーフレ追加 - %s】", fno, round((fno / fnos[-1]) * 100, 3), bone_name)
                prev_sep_fno = fno // 1000

        logger.info("-- IK焼き込み準備:終了【%s】", bone_name)

        # モデルのIKボーンのリンク
        target_links = model.create_link_2_top_one(bone_name, is_defined=False)

        # モデルのIKリンク
        if not (ik_bone.ik.target_index in model.bone_indexes and model.bone_indexes[ik_bone.ik.target_index] in model.bones):
            raise SizingException("{0} のTargetが有効なINDEXではありません。PMXの構造を確認してください。".format(bone_name))

        # IKエフェクタ
        effector_bone_name = model.bone_indexes[ik_bone.ik.target_index]
        effector_links = model.create_link_2_top_one(effector_bone_name, is_defined=False)
        ik_links = BoneLinks()

        # 末端にエフェクタ
        effector_bone = model.bones[effector_bone_name].copy()
        effector_bone.degree_limit = math.degrees(ik_bone.ik.limit_radian)
        ik_links.append(effector_bone)

        for ik_link in ik_bone.ik.link:
            # IKリンクを末端から順に追加
            if not (ik_link.bone_index in model.bone_indexes and model.bone_indexes[ik_link.bone_index] in model.bones):
                raise SizingException("{0} のLinkに無効なINDEXが含まれています。PMXの構造を確認してください。".format(bone_name))
            
            link_bone = model.bones[model.bone_indexes[ik_link.bone_index]].copy()

            if link_bone.fixed_axis != MVector3D():
                # 捩り系は無視
                continue

            # 単位角
            link_bone.degree_limit = math.degrees(ik_bone.ik.limit_radian)

            # 角度制限
            if ik_link.limit_angle == 1:
                link_bone.limit_min = ik_link.limit_min
                link_bone.limit_max = ik_link.limit_max

            ik_links.append(link_bone)

        # ＩＫ以降のリンク
        ik_limit_links = ik_links.to_links(bone_name)

        # 回転移管先ボーン
        transferee_bone = self.get_transferee_bone(ik_bone, effector_bone)

        # 移管先ボーンのローカル軸
        transferee_local_x_axis = model.get_local_x_axis(transferee_bone.name)
        transferee_local_z_axis = MVector3D(0, 0, -1)
        transferee_local_y_axis = MVector3D.crossProduct(transferee_local_x_axis, transferee_local_z_axis).normalized()

        # IKボーンのローカル軸
        ik_local_x_axis = ik_bone.local_x_vector if ik_bone.local_x_vector != MVector3D() else MVector3D(1, 0, 0)

        # 念のためキーフレ再取得
        fnos = motion.get_bone_fnos(bone_name)

        org_motion = motion.copy()

        # 元モーションを保持したら、IKキーフレ削除
        del motion.bones[bone_name]

        for fno in fnos:
            # グローバル位置計算(元モーションの位置)
            global_3ds = MServiceUtils.calc_global_pos(model, target_links, org_motion, fno)
            target_effector_pos = global_3ds[bone_name]

            prev_diff = MVector3D()

            org_bfs = {}
            for link_name in list(ik_links.all().keys())[1:]:
                # 元モーションの角度で保持
                bf = org_motion.calc_bf(link_name, fno).copy()
                org_bfs[link_name] = bf
                # 今のモーションも前のキーフレをクリアして再セット
                motion.regist_bf(bf, link_name, fno)

            # IK計算実行
            for ik_cnt in range(ik_bone.ik.loop):
                MServiceUtils.calc_IK(model, effector_links, motion, fno, target_effector_pos, ik_links, max_count=1)

                # どちらにせよ一旦bf確定
                for link_name in list(ik_links.all().keys())[1:]:
                    ik_bf = motion.calc_bf(link_name, fno)
                    motion.regist_bf(ik_bf, link_name, fno)

                # 現在のエフェクタ位置
                now_global_3ds = MServiceUtils.calc_global_pos(model, effector_links, motion, fno)
                now_effector_pos = now_global_3ds[effector_bone_name]

                # 現在のエフェクタ位置との差分(エフェクタ位置が指定されている場合のみ)
                diff_pos = MVector3D() if target_effector_pos == MVector3D() else target_effector_pos - now_effector_pos

                if prev_diff == MVector3D() or (prev_diff != MVector3D() and diff_pos.length() < prev_diff.length()):
                    if diff_pos.length() < 0.1:
                        logger.test("☆IK焼き込み成功(%s): f: %s(%s), 指定 [%s], 現在[%s], 差異[%s(%s)]", ik_cnt, fno, bone_name, \
                                    target_effector_pos.to_log(), now_effector_pos.to_log(), diff_pos.to_log(), diff_pos.length())

                        # org_bfを保持し直し
                        for link_name in list(ik_links.all().keys())[1:]:
                            bf = motion.calc_bf(link_name, fno).copy()
                            org_bfs[link_name] = bf
                            logger.test("org_bf保持: %s [%s]", link_name, bf.rotation.toEulerAngles().to_log())

                        # そのまま終了
                        break
                    elif prev_diff == MVector3D() or diff_pos.length() < prev_diff.length():
                        logger.test("☆IK焼き込みちょっと失敗採用(%s): f: %s(%s), 指定 [%s], 現在[%s], 差異[%s(%s)]", ik_cnt, fno, bone_name, \
                                    target_effector_pos.to_log(), now_effector_pos.to_log(), diff_pos.to_log(), diff_pos.length())

                        # org_bfを保持し直し
                        for link_name in list(ik_links.all().keys())[1:]:
                            bf = motion.calc_bf(link_name, fno).copy()
                            org_bfs[link_name] = bf
                            logger.test("org_bf保持: %s [%s]", link_name, bf.rotation.toEulerAngles().to_log())

                        # 前回とまったく同じ場合か、充分に近い場合、IK的に動きがないので終了
                        if prev_diff == diff_pos or np.count_nonzero(np.where(np.abs(diff_pos.data()) > 0.05, 1, 0)) == 0:
                            logger.debug("動きがないので終了")
                            break

                        # 前回差異を保持
                        prev_diff = diff_pos
                    else:
                        logger.test("★IK焼き込みちょっと失敗不採用(%s): f: %s(%s), 指定 [%s], 現在[%s], 差異[%s(%s)]", ik_cnt, fno, bone_name, \
                                    target_effector_pos.to_log(), now_effector_pos.to_log(), diff_pos.to_log(), diff_pos.length())

                        # 前回とまったく同じ場合か、充分に近い場合、IK的に動きがないので終了
                        if prev_diff == diff_pos or np.count_nonzero(np.where(np.abs(diff_pos.data()) > 0.05, 1, 0)) == 0:
                            break
                else:
                    logger.test("★IK焼き込み失敗(%s): f: %s(%s), 指定 [%s], 現在[%s], 差異[%s(%s)]", ik_cnt, fno, bone_name, \
                                target_effector_pos.to_log(), now_effector_pos.to_log(), diff_pos.to_log(), diff_pos.length())

                    # 前回とまったく同じ場合か、充分に近い場合、IK的に動きがないので終了
                    if prev_diff == diff_pos or np.count_nonzero(np.where(np.abs(diff_pos.data()) > 0.05, 1, 0)) == 0:
                        logger.debug("動きがないので終了")
                        break
            
            # 最後に成功したところに戻す
            for link_name in list(ik_links.all().keys())[1:]:
                bf = org_bfs[link_name].copy()
                logger.debug("確定org_bf: %s [%s]", link_name, bf.rotation.toEulerAngles().to_log())
                motion.regist_bf(bf, link_name, fno)

            # IKターゲットの回転量を移管
            ik_bf = org_motion.calc_bf(bone_name, fno)
            # IKの親までは認識
            ik_parent_bf = org_motion.calc_bf("{0}親".format(bone_name), fno)
            # 移管グローバル角度（IKボーンの角度に基づく）
            ik_qq = ik_parent_bf.rotation * ik_bf.rotation
            logger.debug("ik_qq: %s [%s]", transferee_bone.name, ik_qq.toEulerAngles().to_log())

            # ローカル軸の角度に変換
            ik_local_x_qq, ik_local_y_qq, ik_local_z_qq, ik_local_yz_qq = MServiceUtils.separate_local_qq(fno, bone_name, ik_qq, transferee_local_x_axis)
            logger.debug("ik_local_x_qq: %s [%s]", transferee_bone.name, ik_local_x_qq.toEulerAngles().to_log())
            logger.debug("ik_local_y_qq: %s [%s]", transferee_bone.name, ik_local_y_qq.toEulerAngles().to_log())
            logger.debug("ik_local_z_qq: %s [%s]", transferee_bone.name, ik_local_z_qq.toEulerAngles().to_log())
            logger.debug("ik_local_yz_qq: %s [%s]", transferee_bone.name, ik_local_yz_qq.toEulerAngles().to_log())

            ik_global_x_qq = MQuaternion.fromAxisAndAngle(transferee_local_x_axis, ik_local_x_qq.toDegree())
            ik_global_y_qq = MQuaternion.fromAxisAndAngle(transferee_local_y_axis, ik_local_y_qq.toDegree())
            ik_global_z_qq = MQuaternion.fromAxisAndAngle(transferee_local_z_axis, ik_local_z_qq.toDegree())
            logger.debug("ik_global_x_qq: %s [%s]", transferee_bone.name, ik_global_x_qq.toEulerAngles().to_log())
            logger.debug("ik_global_y_qq: %s [%s]", transferee_bone.name, ik_global_y_qq.toEulerAngles().to_log())
            logger.debug("ik_global_z_qq: %s [%s]", transferee_bone.name, ik_global_z_qq.toEulerAngles().to_log())

            transferee_bf = motion.calc_bf(transferee_bone.name, fno)
            transferee_bf.rotation = (ik_global_x_qq * ik_local_yz_qq) * transferee_bf.rotation

            logger.debug("transferee_qq: %s [%s]", transferee_bone.name, transferee_bf.rotation.toEulerAngles().to_log())
            motion.regist_bf(transferee_bf, transferee_bone.name, fno)
            
            logger.info("-- %sフレーム目:終了(%s％)【IK焼き込み - %s】", fno, round((fno / fnos[-1]) * 100, 3), bone_name)

    # IKターゲットの回転量移管先を取得
    # 現在のターゲットが表示されてない場合、子で同じ位置にあるのを採用
    def get_transferee_bone(self, ik_bone: Bone, effector_bone: Bone):
        if effector_bone.getVisibleFlag():
            # エフェクタが表示対象なら、エフェクタ自身
            return effector_bone

        # エフェクタが表示対象外なら、子ボーンの中から、同じ位置のを取得

        # 子ボーンリスト取得
        child_bones = self.options.model.get_child_bones(ik_bone)

        for cbone in child_bones:
            if cbone.position.to_log() == effector_bone.position.to_log():
                return cbone

        # 最後まで取れなければ、とりあえずエフェクタ
        return effector_bone



