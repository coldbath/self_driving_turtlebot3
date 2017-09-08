#!/usr/bin/env python

import rospy
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Int16
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
import math
import tf
import numpy as np
from std_msgs.msg import String
## developping...


def distance_dot2line(a, b, c, x0, y0):
    distance = abs(x0*a + y0*b + c)/math.sqrt(a*a + b*b)
    return distance

def distance_dot2dot(x1, y1, x2, y2):
    distance = math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1)*(y2-y1))
    return distance


def theta_dot2dot(start, end):
    theta = math.atan2(end[1]-start[1], end[0]-start[0])
    return theta

def euler_from_quaternion(rot):
    quaternion = (rot)
    theta = tf.transformations.euler_from_quaternion(quaternion)[2]
    return theta

def sign(num):
    if num < 0:
        return -1
    else:
        return 1



class Orientation(object):
    def __init__(self, trans, rot):
        self.x = trans[0]
        self.y = trans[1]
        self.theta = euler_from_quaternion(rot)


class Maze_pathfinder():
    def __init__(self):

        self._sub = rospy.Subscriber('/map', OccupancyGrid, self.callback, queue_size=1)
        self._sub = rospy.Subscriber('/odom', Odometry, self.callback2, queue_size=1)
        self._sub = rospy.Subscriber('/scan', LaserScan, self.callback3, queue_size=1)

        self._pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self._pub2 = rospy.Publisher('/maze', String, queue_size=1)

        self.state = 'setting_start_and_goal' # path_finding, stop, going, direction_setting

        # variables used in maze solve

        self.sell_size = 0.1
        self.car_size = 0.1


        # variables used in move to enterance and exit
        self.position_now = None
        self.theta_now = None

        self.scan = None
        self.start_point = None

        self.current_direction = None
        self.angle_from_direction = {'top':0, 'left':np.pi/2, 'bottom':np.pi, 'right':np.pi*3/2}


    def callback2(self, odometry):
        self.position_now = [odometry.pose.pose.position.x, odometry.pose.pose.position.y]
        quaternion = (odometry.pose.pose.orientation.x, odometry.pose.pose.orientation.y, odometry.pose.pose.orientation.z, odometry.pose.pose.orientation.w)
        self.theta_now = euler_from_quaternion(quaternion)


        if self.state == "setting_start_and_goal":
            min_distance = 100
            for i in range(90,180):
                if self.scan.ranges[i] < min_distance:
                    min_distance = self.scan.ranges[i]
                    idx_1 = i
            min_distance = 100
            for i in range(0,90):
                if self.scan.ranges[i] < min_distance:
                    min_distance = self.scan.ranges[i]
                    idx_2 = i
            point1 = [self.position_now[0] + self.scan.ranges[idx_1] * math.cos(idx_1 * np.pi/180), self.position_now[1] + self.scan.ranges[idx_1] * math.sin(idx_1 * np.pi/180)]
            point2 = [self.position_now[0] + self.scan.ranges[idx_2] * math.cos(idx_2 * np.pi/180), self.position_now[1] + self.scan.ranges[idx_2] * math.sin(idx_2 * np.pi/180)]
            between_point1_point2 = [(point1[0] + point2[0])/2, (point1[1] + point2[1])/2]

            # defining start point
            angle = theta_dot2dot(point1, point2)
            self.start_point = [between_point1_point2[0] + math.cos(angle + np.pi/2) * 0.1, between_point1_point2[1] + math.sin(angle + np.pi/2) * 0.1]

            # defining end point
            angle = theta_dot2dot(point2, point1)
            self.theta_exit = angle
            distance_axis_x = [1.6*math.cos(angle), 1.6*math.sin(angle)]
            distance_axis_y = [1.6*math.cos(angle - np.pi/2), 1.6*math.sin(angle - np.pi/2)]
            self.end_point = [self.start_point[0] + distance_axis_x[0] + distance_axis_y[0], self.start_point[1] + distance_axis_x[1] + distance_axis_y[1]]

            self.state = "move_to_start_point"

        if self.state == "move_to_start_point":
            self.move_to_some_point(self.position_now, self.theta_now, self.start_point)
            distance_remain = distance_dot2dot(self.position_now[0], self.position_now[1], self.start_point[0], self.start_point[1])
            if distance_remain < 0.02:
                self.current_direction = "top"
                self.state = "path_finding" # now maze solve start!!

        if self.state == "path_finding":
            if self.current_direction == "top":
                obstacle = self.obs_check("right", self.current_direction)
                if obstacle == "no":
                    self.state = "moing"
                    self.current_direction = "right"
                else:
                    obstacle = self.obs_check("top", self.current_direction)
                    if obstacle == "no":
                        self.state = "moving"
                        self.current_direction = "top"
                    else:
                        self.state = "moving"
                        self.current_direction = "left"

            if self.current_direction == "left":
                obstacle = self.obs_check("top", self.current_direction)
                if obstacle == "no":
                    self.state = "moing"
                    self.current_direction = "top"
                else:
                    obstacle = self.obs_check("left", self.current_direction)
                    if obstacle == "no":
                        self.state = "moving"
                        self.current_direction = "left"
                    else:
                        self.state = "moving"
                        self.current_direction = "bottom"

            if self.current_direction == "bottom":
                obstacle = self.obs_check("left", self.current_direction)
                if obstacle == "no":
                    self.state = "moing"
                    self.current_direction = "left"
                else:
                    obstacle = self.obs_check("bottom", self.current_direction)
                    if obstacle == "no":
                        self.state = "moving"
                        self.current_direction = "bottom"
                    else:
                        self.state = "moving"
                        self.current_direction = "right"

            if self.current_direction == "right":
                obstacle = self.obs_check("bottom", self.current_direction)
                if obstacle == "no":
                    self.state = "moing"
                    self.current_direction = "bottom"
                else:
                    obstacle = self.obs_check("right", self.current_direction)
                    if obstacle == "no":
                        self.state = "moving"
                        self.current_direction = "top"
                    else:
                        self.state = "moving"
                        self.current_direction = "right"
        self.move()

    def obs_check(self,check_direction, current_direction):
        self.cell = np.zeros((6,4), np.uint8)
        obstacle = "no"
        for i in range(180):
            x_pose = math.cos(i*np.pi/180 + self.angle_from_direction[check_direction] - self.angle_from_direction[current_direction])*self.scan.ranges[i]
            y_pose = math.sin(i*np.pi/180 + self.angle_from_direction[check_direction] - self.angle_from_direction[current_direction])*self.scan.ranges[i]
            if abs(x_pose) < 0.15 and y_pose < 0.20:
                obstacle = "yes"
                if x_pose > 0:
                    x_num = 3 + int(x_pose*20)
                else:
                    x_num = 2 - int(abs(x_pose)*20)
                y_num = int(y_pose*20)
                self.cell[x_num][y_num] = 1
        return obstacle

    def move(self):
        a =1

    def move_left(self):
        a=1
    def move_right(self):
        a=1
    def move_top(self):
        a=1
    def move_bottom(self):
        a=1

    def callback3(self, scan):
        self.scan = scan


        for i in range(360):
            if scan.ranges[(i + 270) % 360] != 0:
                self.scan.ranges[i] = scan.ranges[(i + 270) % 360]
            else:
                self.scan.ranges[i] = 3



    def move_to_some_point(self, position_now, theta_now, position_desired):
        theta_desired = theta_dot2dot(position_now, position_desired)
        diff = abs(theta_desired - theta_now)
        if diff > 2*np.pi:
            diff -= 2*np.pi
        if diff > np.pi/100:
            print 'diff', abs(theta_desired - theta_now)
            self.setting_angle(theta_now, theta_desired)
        else:
            self.going_straight()



    def setting_angle(self, theta_now, theta_desired):
        if theta_desired < 0:
            theta_desired += np.pi*2
        print 'setting angle'
        print theta_now
        print theta_desired
        if theta_desired > theta_now:
            if theta_desired - theta_now < np.pi:
                turn_direction = 'left'
            else:
                turn_direction = 'right'
        else:
            if theta_now - theta_desired < np.pi:
                turn_direction = 'right'
            else:
                turn_direction = 'left'
                # publish topic
        difference = abs(theta_desired - theta_now)
        if difference > np.pi:
            difference = np.pi * 2 - difference
        if difference > 0.3:
            turn_speed = 0.6
        elif difference > 0.2:
            turn_speed = 0.3
        elif difference > 0.1:
            turn_speed = 0.1
        elif difference > 0.01:
            turn_speed = 0.05
        else:
            turn_speed = 0
        if turn_direction == 'left':
            ang_z = turn_speed
        else:
            ang_z = - turn_speed
        self.publishing_vel(0, 0, 0, 0, 0, ang_z)

    def going_straight(self):
        print 'going straight'
        print self.position_now
        print self.theta_now
        print self.position_parking
        self.publishing_vel(0.06, 0, 0, 0, 0, 0)

    def publishing_vel(self, angular_x, angular_y, angular_z, linear_x, linear_y, linear_z):
        vel = Twist()
        vel.angular.x = angular_x
        vel.angular.y = angular_y
        vel.angular.z = angular_z
        vel.linear.x = linear_x
        vel.linear.y = linear_y
        vel.linear.z = linear_z
        self._pub.publish(vel)

    def main(self):
        rospy.spin()

if __name__ == '__main__':
    rospy.init_node('maze_pathfinder')
    mazesolver = Maze_pathfinder()
    mazesolver.main()