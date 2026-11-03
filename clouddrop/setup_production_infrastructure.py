#!/usr/bin/env python3
"""
CloudDrop Production Infrastructure Setup Script
Configures:
1. S3 Bucket Policy (TLS enforcement + Role permissions)
2. S3 CORS Policy (Full web client access)
3. CloudWatch Operations Dashboard (EC2, SQS, RDS, S3 metrics)
4. Application Load Balancer (ALB) + Target Group + Auto Scaling Group
"""

import boto3
import json
import sys
import time

REGION = "us-east-1"
ACCOUNT_ID = "205839628513"
VPC_ID = "vpc-06e4f0ecc87b1ac52"
SUBNETS = ["subnet-02b0a4e2fc3985d03", "subnet-08e77798b5fe9cac3"]
INSTANCE_ID = "i-041d9c437d77036dc"
INSTANCE_SG = "sg-09942c6b9fc5a0169"
BUCKET_NAME = "clouddrop-media-23871"
QUEUE_NAME = "clouddrop-jobs"
RDS_INSTANCE_ID = "clouddrop-db"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/clouddrop-ec2-role"

s3 = boto3.client("s3", region_name=REGION)
cw = boto3.client("cloudwatch", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)
autoscaling = boto3.client("autoscaling", region_name=REGION)

def setup_s3_cors():
    print("[1/4] Applying S3 CORS Policy...")
    cors_configuration = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT", "POST", "HEAD", "DELETE"],
                "AllowedOrigins": ["*"],
                "ExposeHeaders": ["ETag", "Content-Disposition", "Content-Length"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }
    s3.put_bucket_cors(Bucket=BUCKET_NAME, CORSConfiguration=cors_configuration)
    print("  ✓ S3 CORS Policy applied successfully.")

def setup_s3_policy():
    print("[2/4] Applying S3 Bucket Policy...")
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "EnforceTLSRequestsOnly",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{BUCKET_NAME}",
                    f"arn:aws:s3:::{BUCKET_NAME}/*"
                ],
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false"
                    }
                }
            },
            {
                "Sid": "AllowCloudDropAppAccess",
                "Effect": "Allow",
                "Principal": {
                    "AWS": ROLE_ARN
                },
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{BUCKET_NAME}",
                    f"arn:aws:s3:::{BUCKET_NAME}/*"
                ]
            }
        ]
    }
    s3.put_bucket_policy(Bucket=BUCKET_NAME, Policy=json.dumps(bucket_policy))
    print("  ✓ S3 Bucket Policy applied successfully.")

def setup_cloudwatch_dashboard():
    print("[3/4] Creating CloudWatch Production Dashboard...")
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0, "y": 0, "width": 24, "height": 2,
                "properties": {
                    "markdown": "# 🚀 CloudDrop PDF Suite - Production Operational Metrics\nMonitoring EC2 Compute, SQS Message Queue, RDS PostgreSQL, and S3 Storage."
                }
            },
            {
                "type": "metric",
                "x": 0, "y": 2, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/EC2", "CPUUtilization", "InstanceId", INSTANCE_ID, {"label": "EC2 CPU %", "color": "#1f77b4"}],
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": REGION,
                    "title": "EC2 Compute CPU Utilization"
                }
            },
            {
                "type": "metric",
                "x": 12, "y": 2, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", QUEUE_NAME, {"label": "Pending Jobs (Queue Backlog)", "color": "#ff7f0e"}],
                        ["AWS/SQS", "ApproximateNumberOfMessagesNotVisible", "QueueName", QUEUE_NAME, {"label": "Jobs Currently Processing", "color": "#2ca02c"}],
                    ],
                    "period": 60,
                    "stat": "Maximum",
                    "region": REGION,
                    "title": "SQS Job Queue Depth & Active Tasks"
                }
            },
            {
                "type": "metric",
                "x": 0, "y": 8, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", RDS_INSTANCE_ID, {"label": "RDS CPU %", "color": "#d62728"}],
                        ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", RDS_INSTANCE_ID, {"label": "Active DB Connections", "yAxis": "right", "color": "#9467bd"}],
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": REGION,
                    "title": "RDS PostgreSQL Health & Connections"
                }
            },
            {
                "type": "metric",
                "x": 12, "y": 8, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/SQS", "NumberOfMessagesSent", "QueueName", QUEUE_NAME, {"label": "Jobs Enqueued", "stat": "Sum"}],
                        ["AWS/SQS", "NumberOfMessagesDeleted", "QueueName", QUEUE_NAME, {"label": "Jobs Finished", "stat": "Sum"}],
                    ],
                    "period": 60,
                    "stat": "Sum",
                    "region": REGION,
                    "title": "Job Throughput (Enqueued vs Processed)"
                }
            }
        ]
    }
    cw.put_dashboard(
        DashboardName="CloudDrop-Platform-Monitor",
        DashboardBody=json.dumps(dashboard_body)
    )
    print("  ✓ CloudWatch Dashboard 'CloudDrop-Platform-Monitor' created.")

def setup_load_balancing_and_asg():
    print("[4/4] Setting up Application Load Balancer & Auto Scaling Group...")
    
    # 1. Create or get ALB Security Group
    alb_sg_name = "clouddrop-alb-sg"
    sgs = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [alb_sg_name]}, {"Name": "vpc-id", "Values": [VPC_ID]}])["SecurityGroups"]
    if sgs:
        alb_sg_id = sgs[0]["GroupId"]
        print(f"  ALB Security Group exists: {alb_sg_id}")
    else:
        sg_res = ec2.create_security_group(
            GroupName=alb_sg_name,
            Description="Security group for CloudDrop Application Load Balancer",
            VpcId=VPC_ID
        )
        alb_sg_id = sg_res["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=alb_sg_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP Web"}]}
            ]
        )
        print(f"  Created ALB Security Group: {alb_sg_id}")

    # 2. Target Group
    tg_name = "clouddrop-tg"
    tgs = elbv2.describe_target_groups(Names=[tg_name])["TargetGroups"] if _tg_exists(tg_name) else []
    if tgs:
        tg_arn = tgs[0]["TargetGroupArn"]
        print(f"  Target Group exists: {tg_arn}")
    else:
        tg_res = elbv2.create_target_group(
            Name=tg_name,
            Protocol="HTTP",
            Port=80,
            VpcId=VPC_ID,
            HealthCheckProtocol="HTTP",
            HealthCheckPort="80",
            HealthCheckPath="/api/health",
            HealthCheckIntervalSeconds=30,
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=3,
            Matcher={"HttpCode": "200"},
            TargetType="instance"
        )
        tg_arn = tg_res["TargetGroups"][0]["TargetGroupArn"]
        print(f"  Created Target Group: {tg_arn}")

    # Register existing EC2 instance into Target Group
    elbv2.register_targets(TargetGroupArn=tg_arn, Targets=[{"Id": INSTANCE_ID, "Port": 80}])
    print(f"  Registered EC2 instance {INSTANCE_ID} into Target Group.")

    # 3. Application Load Balancer
    alb_name = "clouddrop-alb"
    albs = elbv2.describe_load_balancers(Names=[alb_name])["LoadBalancers"] if _alb_exists(alb_name) else []
    if albs:
        alb_arn = albs[0]["LoadBalancerArn"]
        alb_dns = albs[0]["DNSName"]
        print(f"  ALB exists: {alb_dns}")
    else:
        alb_res = elbv2.create_load_balancer(
            Name=alb_name,
            Subnets=SUBNETS,
            SecurityGroups=[alb_sg_id, INSTANCE_SG],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4"
        )
        alb_arn = alb_res["LoadBalancers"][0]["LoadBalancerArn"]
        alb_dns = alb_res["LoadBalancers"][0]["DNSName"]
        print(f"  Created ALB: {alb_dns}")

    # 4. Listener
    listeners = elbv2.describe_listeners(LoadBalancerArn=alb_arn)["Listeners"]
    if not listeners:
        elbv2.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}]
        )
        print("  Created Port 80 HTTP Listener on ALB.")

    # 5. Launch Template & Auto Scaling Group
    lt_name = "clouddrop-lt"
    lts = ec2.describe_launch_templates(LaunchTemplateNames=[lt_name])["LaunchTemplates"] if _lt_exists(lt_name) else []
    if lts:
        print(f"  Launch Template exists: {lt_name}")
    else:
        ec2.create_launch_template(
            LaunchTemplateName=lt_name,
            LaunchTemplateData={
                "InstanceType": "t3.micro",
                "SecurityGroupIds": [INSTANCE_SG],
                "IamInstanceProfile": {"Arn": f"arn:aws:iam::{ACCOUNT_ID}:instance-profile/clouddrop-ec2-role"},
                "TagSpecifications": [
                    {
                        "ResourceType": "instance",
                        "Tags": [{"Key": "Name", "Value": "clouddrop-worker-asg"}]
                    }
                ]
            }
        )
        print(f"  Created Launch Template: {lt_name}")

    asg_name = "clouddrop-asg"
    asgs = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"]
    if asgs:
        print(f"  Auto Scaling Group exists: {asg_name}")
    else:
        autoscaling.create_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            LaunchTemplate={"LaunchTemplateName": lt_name, "Version": "$Latest"},
            MinSize=1,
            MaxSize=3,
            DesiredCapacity=1,
            VPCZoneIdentifier=",".join(SUBNETS),
            TargetGroupARNs=[tg_arn],
            HealthCheckType="ELB",
            HealthCheckGracePeriod=300
        )
        print(f"  Created Auto Scaling Group: {asg_name} (Min: 1, Desired: 1, Max: 3)")

        # SQS Target Tracking Scaling Policy
        autoscaling.put_scaling_policy(
            AutoScalingGroupName=asg_name,
            PolicyName="clouddrop-sqs-backlog-scaleout",
            PolicyType="TargetTrackingScaling",
            TargetTrackingConfiguration={
                "CustomizedMetricSpecification": {
                    "MetricName": "ApproximateNumberOfMessagesVisible",
                    "Namespace": "AWS/SQS",
                    "Dimensions": [{"Name": "QueueName", "Value": QUEUE_NAME}],
                    "Statistic": "Sum"
                },
                "TargetValue": 10.0
            }
        )
        print("  Attached SQS Queue Backlog Scaling Policy.")

    return alb_dns

def _tg_exists(name):
    try:
        elbv2.describe_target_groups(Names=[name])
        return True
    except Exception:
        return False

def _alb_exists(name):
    try:
        elbv2.describe_load_balancers(Names=[name])
        return True
    except Exception:
        return False

def _lt_exists(name):
    try:
        ec2.describe_launch_templates(LaunchTemplateNames=[name])
        return True
    except Exception:
        return False

if __name__ == "__main__":
    print("=== CloudDrop Production Infrastructure Provisioner ===")
    setup_s3_cors()
    setup_s3_policy()
    setup_cloudwatch_dashboard()
    alb_dns = setup_load_balancing_and_asg()
    print("\n[SUCCESS] All infrastructure components configured!")
    print(f"ALB Endpoint: http://{alb_dns}")
