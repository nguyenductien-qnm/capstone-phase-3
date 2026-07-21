import json
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client('ec2')
eks = boto3.client('eks')
rds = boto3.client('rds')
elasticache = boto3.client('elasticache')
autoscaling = boto3.client('autoscaling')


def handler(event, context):
    """
    Lambda handler nhận SNS trigger từ AWS Budget Alarms
    và thực hiện scale down/stop resources dựa trên chi phí
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse SNS message
        message = event['Records'][0]['Sns']['Message']
        logger.info(f"Budget alarm message: {message}")
        
        # Xác định ngưỡng (80% hay 95%) dựa trên TopicArn thay vì Subject
        topic_arn = event['Records'][0]['Sns'].get('TopicArn', '')
        is_critical = topic_arn.endswith('-95') or 'budget-alarms-95' in topic_arn
        alert_subject = event['Records'][0]['Sns'].get('Subject', '')
        
        logger.info(f"Alert type - Critical (95%): {is_critical}")
        
        # Ghi log thông tin cảnh báo
        timestamp = datetime.utcnow().isoformat()
        alert_info = {
            "timestamp": timestamp,
            "is_critical": is_critical,
            "subject": alert_subject,
            "message": message
        }
        logger.info(f"Alert info: {json.dumps(alert_info)}")
        
        results = {
            "timestamp": timestamp,
            "alert_type": "CRITICAL" if is_critical else "WARNING",
            "actions_taken": []
        }
        
        # Lấy thông tin từ environment variables
        eks_cluster_name = os.environ.get('EKS_CLUSTER_NAME')
        rds_instances = json.loads(os.environ.get('RDS_INSTANCE_IDENTIFIERS', '[]'))
        elasticache_clusters = json.loads(os.environ.get('ELASTICACHE_CLUSTER_IDS', '[]'))
        ec2_tag_key = os.environ.get('EC2_INSTANCE_TAG_KEY')
        ec2_tag_value = os.environ.get('EC2_INSTANCE_TAG_VALUE')
        asg_names = json.loads(os.environ.get('AUTO_SCALING_GROUP_NAMES', '[]'))
        
        # Thực hiện actions dựa trên mức cảnh báo
        if is_critical:  # 95% - Critical threshold
            logger.info("Executing CRITICAL actions (95% threshold)")
            
            # Scale down EKS nodes
            if eks_cluster_name:
                eks_result = scale_down_eks_nodes(eks_cluster_name)
                results["actions_taken"].append(eks_result)
            
            # Stop RDS instances
            if rds_instances:
                rds_result = stop_rds_instances(rds_instances)
                results["actions_taken"].append(rds_result)
            
            # Reduce ElastiCache nodes
            if elasticache_clusters:
                cache_result = reduce_elasticache_clusters(elasticache_clusters)
                results["actions_taken"].append(cache_result)
            
            # Stop EC2 instances with tags
            if ec2_tag_key and ec2_tag_value:
                ec2_result = stop_ec2_instances(ec2_tag_key, ec2_tag_value)
                results["actions_taken"].append(ec2_result)
            
            # Scale down Auto Scaling Groups
            if asg_names:
                asg_result = scale_down_auto_scaling_groups(asg_names)
                results["actions_taken"].append(asg_result)
        
        else:  # 80% - Warning threshold
            logger.info("Executing WARNING actions (80% threshold)")
            
            # Scale down EKS nodes to 50%
            if eks_cluster_name:
                eks_result = scale_down_eks_nodes_partial(eks_cluster_name, 0.5)
                results["actions_taken"].append(eks_result)
            
            # Scale down Auto Scaling Groups to 50%
            if asg_names:
                asg_result = scale_down_auto_scaling_groups_partial(asg_names, 0.5)
                results["actions_taken"].append(asg_result)
        
        logger.info(f"Execution results: {json.dumps(results)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(results)
        }
    
    except Exception as e:
        logger.error(f"Error processing budget alert: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }


def scale_down_eks_nodes(cluster_name):
    """Scale down EKS node group"""
    try:
        logger.info(f"Scaling down EKS cluster: {cluster_name}")
        
        # Get node groups
        response = eks.list_nodegroups(clusterName=cluster_name)
        nodegroups = response.get('nodegroups', [])
        
        actions = []
        for ng in nodegroups:
            try:
                # Get current nodegroup config
                ng_info = eks.describe_nodegroup(
                    clusterName=cluster_name,
                    nodegroupName=ng
                )
                
                current_scaling = ng_info['nodegroup'].get('scalingConfig', {})
                desired = current_scaling.get('desiredSize', 1)
                
                # Scale down to 0
                eks.update_nodegroup_config(
                    clusterName=cluster_name,
                    nodegroupName=ng,
                    scalingConfig={
                        'minSize': 0,
                        'maxSize': 1,
                        'desiredSize': 0
                    }
                )
                
                actions.append({
                    'resource': f'EKS-NodeGroup:{ng}',
                    'action': 'scale_down',
                    'from': desired,
                    'to': 0,
                    'status': 'success'
                })
                logger.info(f"Successfully scaled down nodegroup {ng} from {desired} to 0")
            
            except Exception as e:
                logger.error(f"Error scaling down nodegroup {ng}: {str(e)}")
                actions.append({
                    'resource': f'EKS-NodeGroup:{ng}',
                    'action': 'scale_down',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'EKS',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in scale_down_eks_nodes: {str(e)}")
        return {
            'resource_type': 'EKS',
            'status': 'failed',
            'error': str(e)
        }


def scale_down_eks_nodes_partial(cluster_name, scale_factor):
    """Partial scale down EKS nodes (80% threshold)"""
    try:
        logger.info(f"Partial scaling down EKS cluster: {cluster_name} to {scale_factor*100}%")
        
        response = eks.list_nodegroups(clusterName=cluster_name)
        nodegroups = response.get('nodegroups', [])
        
        actions = []
        for ng in nodegroups:
            try:
                ng_info = eks.describe_nodegroup(
                    clusterName=cluster_name,
                    nodegroupName=ng
                )
                
                current_scaling = ng_info['nodegroup'].get('scalingConfig', {})
                desired = current_scaling.get('desiredSize', 1)
                new_desired = max(1, int(desired * scale_factor))
                
                eks.update_nodegroup_config(
                    clusterName=cluster_name,
                    nodegroupName=ng,
                    scalingConfig={
                        'minSize': 1,
                        'maxSize': desired,
                        'desiredSize': new_desired
                    }
                )
                
                actions.append({
                    'resource': f'EKS-NodeGroup:{ng}',
                    'action': 'partial_scale_down',
                    'from': desired,
                    'to': new_desired,
                    'status': 'success'
                })
                logger.info(f"Successfully partially scaled down nodegroup {ng} from {desired} to {new_desired}")
            
            except Exception as e:
                logger.error(f"Error partial scaling nodegroup {ng}: {str(e)}")
                actions.append({
                    'resource': f'EKS-NodeGroup:{ng}',
                    'action': 'partial_scale_down',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'EKS-Partial',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in scale_down_eks_nodes_partial: {str(e)}")
        return {
            'resource_type': 'EKS-Partial',
            'status': 'failed',
            'error': str(e)
        }


def stop_rds_instances(instance_identifiers):
    """Stop RDS instances"""
    try:
        logger.info(f"Stopping RDS instances: {instance_identifiers}")
        
        actions = []
        for instance_id in instance_identifiers:
            try:
                rds.stop_db_instance(DBInstanceIdentifier=instance_id)
                
                actions.append({
                    'resource': f'RDS:{instance_id}',
                    'action': 'stop',
                    'status': 'success'
                })
                logger.info(f"Successfully stopped RDS instance {instance_id}")
            
            except rds.exceptions.DBInstanceNotFoundFault:
                logger.warning(f"RDS instance {instance_id} not found")
                actions.append({
                    'resource': f'RDS:{instance_id}',
                    'action': 'stop',
                    'status': 'not_found'
                })
            
            except Exception as e:
                logger.error(f"Error stopping RDS instance {instance_id}: {str(e)}")
                actions.append({
                    'resource': f'RDS:{instance_id}',
                    'action': 'stop',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'RDS',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in stop_rds_instances: {str(e)}")
        return {
            'resource_type': 'RDS',
            'status': 'failed',
            'error': str(e)
        }


def reduce_elasticache_clusters(cluster_ids):
    """Reduce ElastiCache cluster nodes"""
    try:
        logger.info(f"Reducing ElastiCache clusters: {cluster_ids}")
        
        actions = []
        for cluster_id in cluster_ids:
            try:
                # Lấy thông tin cluster
                response = elasticache.describe_replication_groups(
                    ReplicationGroupId=cluster_id
                )
                
                if response['ReplicationGroups']:
                    rg = response['ReplicationGroups'][0]
                    current_nodes = len(rg.get('MemberClusters', []))
                    new_nodes = max(1, current_nodes - 1)
                    
                    # Reduce cache nodes
                    elasticache.decrease_replica_count(
                        ReplicationGroupId=cluster_id,
                        NewReplicaCount=new_nodes - 1,
                        ApplyImmediately=True
                    )
                    
                    actions.append({
                        'resource': f'ElastiCache:{cluster_id}',
                        'action': 'reduce_replicas',
                        'from': current_nodes,
                        'to': new_nodes,
                        'status': 'success'
                    })
                    logger.info(f"Successfully reduced ElastiCache cluster {cluster_id} from {current_nodes} to {new_nodes} nodes")
            
            except Exception as e:
                logger.error(f"Error reducing ElastiCache cluster {cluster_id}: {str(e)}")
                actions.append({
                    'resource': f'ElastiCache:{cluster_id}',
                    'action': 'reduce_replicas',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'ElastiCache',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in reduce_elasticache_clusters: {str(e)}")
        return {
            'resource_type': 'ElastiCache',
            'status': 'failed',
            'error': str(e)
        }


def stop_ec2_instances(tag_key, tag_value):
    """Stop EC2 instances với specific tag"""
    try:
        logger.info(f"Stopping EC2 instances with tag {tag_key}={tag_value}")
        
        # Tìm instances với tag
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': f'tag:{tag_key}',
                    'Values': [tag_value]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )
        
        actions = []
        instance_ids = []
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
        
        if instance_ids:
            ec2.stop_instances(InstanceIds=instance_ids)
            
            for instance_id in instance_ids:
                actions.append({
                    'resource': f'EC2:{instance_id}',
                    'action': 'stop',
                    'status': 'success'
                })
                logger.info(f"Successfully stopped EC2 instance {instance_id}")
        
        return {
            'resource_type': 'EC2',
            'instances_stopped': len(instance_ids),
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in stop_ec2_instances: {str(e)}")
        return {
            'resource_type': 'EC2',
            'status': 'failed',
            'error': str(e)
        }


def scale_down_auto_scaling_groups(asg_names):
    """Scale down Auto Scaling Groups"""
    try:
        logger.info(f"Scaling down Auto Scaling Groups: {asg_names}")
        
        actions = []
        for asg_name in asg_names:
            try:
                # Lấy thông tin ASG
                response = autoscaling.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name]
                )
                
                if response['AutoScalingGroups']:
                    asg = response['AutoScalingGroups'][0]
                    current_desired = asg['DesiredCapacity']
                    
                    # Scale down to 0
                    autoscaling.set_desired_capacity(
                        AutoScalingGroupName=asg_name,
                        DesiredCapacity=0,
                        HonorCooldown=False
                    )
                    
                    actions.append({
                        'resource': f'ASG:{asg_name}',
                        'action': 'scale_down',
                        'from': current_desired,
                        'to': 0,
                        'status': 'success'
                    })
                    logger.info(f"Successfully scaled down ASG {asg_name} from {current_desired} to 0")
            
            except Exception as e:
                logger.error(f"Error scaling down ASG {asg_name}: {str(e)}")
                actions.append({
                    'resource': f'ASG:{asg_name}',
                    'action': 'scale_down',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'ASG',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in scale_down_auto_scaling_groups: {str(e)}")
        return {
            'resource_type': 'ASG',
            'status': 'failed',
            'error': str(e)
        }


def scale_down_auto_scaling_groups_partial(asg_names, scale_factor):
    """Partial scale down Auto Scaling Groups (80% threshold)"""
    try:
        logger.info(f"Partial scaling down Auto Scaling Groups: {asg_names} to {scale_factor*100}%")
        
        actions = []
        for asg_name in asg_names:
            try:
                response = autoscaling.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name]
                )
                
                if response['AutoScalingGroups']:
                    asg = response['AutoScalingGroups'][0]
                    current_desired = asg['DesiredCapacity']
                    new_desired = max(1, int(current_desired * scale_factor))
                    
                    autoscaling.set_desired_capacity(
                        AutoScalingGroupName=asg_name,
                        DesiredCapacity=new_desired,
                        HonorCooldown=False
                    )
                    
                    actions.append({
                        'resource': f'ASG:{asg_name}',
                        'action': 'partial_scale_down',
                        'from': current_desired,
                        'to': new_desired,
                        'status': 'success'
                    })
                    logger.info(f"Successfully partially scaled down ASG {asg_name} from {current_desired} to {new_desired}")
            
            except Exception as e:
                logger.error(f"Error partial scaling ASG {asg_name}: {str(e)}")
                actions.append({
                    'resource': f'ASG:{asg_name}',
                    'action': 'partial_scale_down',
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'resource_type': 'ASG-Partial',
            'actions': actions,
            'status': 'completed'
        }
    
    except Exception as e:
        logger.error(f"Error in scale_down_auto_scaling_groups_partial: {str(e)}")
        return {
            'resource_type': 'ASG-Partial',
            'status': 'failed',
            'error': str(e)
        }
