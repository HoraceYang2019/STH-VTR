import config
from CTL_Service import STH_CTL_COMM, STH_CTL_MOTION, ShareVar, STH_CTL_MQTT
def main():
    
    # test.main()
    s_class = ShareVar()
    ctl_comm_thread = STH_CTL_COMM.CtlComm(s_class)
    ctl_motion_thread = STH_CTL_MOTION.CtlMotion(s_class)

    ctl_comm_thread.start()    
    ctl_motion_thread.start()  

    ctl_comm_thread.join()    
    ctl_motion_thread.join()    
    
if __name__ == "__main__":
    # 10.0.0.69
    main()
