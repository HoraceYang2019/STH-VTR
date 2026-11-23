# -*- coding: utf-8 -*-
"""沿用既有檔名；只啟動 COMM 的資料採集流程。"""

from CTL_Service import STH_CTL_COMM


def main():
    STH_CTL_COMM.main_calculation()


if __name__ == "__main__":
    main()
