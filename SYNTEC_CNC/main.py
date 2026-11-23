# -*- coding: utf-8 -*-
"""透過 COMM 啟動 CNC 資料採集。"""

from CTL_Service import STH_CTL_COMM


def main():
    STH_CTL_COMM.main_calculation()


if __name__ == "__main__":
    main()
