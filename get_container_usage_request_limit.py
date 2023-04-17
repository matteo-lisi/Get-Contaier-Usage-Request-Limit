#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from kubernetes import client, config
from openshift.dynamic import DynamicClient
import urllib3
import os
from prometheus_api_client import PrometheusConnect
import datetime
import logging
import argparse


# Set LOG format and Level to view
logging.basicConfig(format='%(asctime)s - [%(levelname)s]: %(message)s', level=logging.INFO)
logging.debug('Start')


# Parse Script Argument
logging.debug('Parse Script Argument')
parser = argparse.ArgumentParser()
parser.add_argument('-n', dest='select_namespace', type=str, help='Select Namespace to be run script')
args = parser.parse_args()


# Set Date and Time
actual_date = datetime.datetime.now()

exclude_projects = [
  'default',
  'glusterfs',
  'kube-public',
  'kube-service-catalog',
  'kube-system',
  'openshift',
  'openshift-console',
  'openshift-infra',
  'openshift-logging',
  'openshift-metrics-server',
  'openshift-migration',
  'openshift-monitoring',
  'openshift-node',
  'openshift-sdn',
  'openshift-template-service-broker',
  'openshift-web-console',
  'stackrox'
]
report_files = {
  'csv_file': {'name': f"Report-pod_consuming-{actual_date.strftime('%Y-%m-%d_%H%M')}.csv",
               'data': ['Namespace;Node;POD;ContainerName;CPU_Request(m);CPU_UsageAVG(m);CPU_UsageMAX(m);CPU_Limit(m);Memory_Request(Mi);Memory_UsageAVG(Mi);Memory_UsageMAX(Mi);Memory_Limit(Mi)']},
  'temp': {}
}

### Disabled Warning for Self-signed SSL Cert
urllib3.disable_warnings()

# Login K8s
## Check if running on POD
if "KUBERNETES_SERVICE_HOST" in os.environ:
    config.load_incluster_config()
else:
    config.load_kube_config()

k8s_client = client.ApiClient()
dyn_client = DynamicClient(k8s_client)
logging.info("K8s Host: %s", k8s_client.configuration.host)
# -------------------------

# Get Prometheus Host
v1_route = dyn_client.resources.get(api_version="route.openshift.io/v1", kind="Route")
prometheus_route = v1_route.get(name='prometheus-k8s', namespace='openshift-monitoring')
prometheus_host = f"https://{prometheus_route.spec.host}"
logging.info('Prometheus Host: %s', prometheus_host)

# Prometheus Login
prom = PrometheusConnect(url=prometheus_host, headers={"Authorization": "{}".format(k8s_client.configuration.api_key['authorization'])}, disable_ssl=True)

# Set Start Time for Prometheus Query
time_range = "2d"
logging.debug('Set Start Time for Prometheus Query --> Set Time Range: %s', time_range)


def get_pod_cpu_memory_usage(project_name,pod_name):
  data = {}
  query_list = {
    'cpu_request': 'avg(kube_pod_container_resource_requests_cpu_cores{namespace="' + project_name + '",pod="' + pod_name + '"}) by (container,namespace,pod,node)',
    'cpu_usage_day': 'avg_over_time(namespace_pod_name_container_name:container_cpu_usage_seconds_total:sum_rate{container_name!="POD",namespace="' + project_name + '",pod_name="' + pod_name + '"}[' + time_range + '])',
    'cpu_usage_day_max': 'max_over_time(namespace_pod_name_container_name:container_cpu_usage_seconds_total:sum_rate{container_name!="POD",namespace="' + project_name + '",pod_name="' + pod_name + '"}[' + time_range + '])',
    'cpu_limit': 'avg(kube_pod_container_resource_limits_cpu_cores{namespace="' + project_name + '",pod="' + pod_name + '"}) by (container,namespace,pod,node)',
    'memory_request': 'kube_pod_container_resource_requests_memory_bytes{namespace="' + project_name + '",pod="' + pod_name + '"}/1024/1024',
    'memory_usage_day': 'avg_over_time(container_memory_usage_bytes{image!="",container_name!="POD",namespace="' + project_name + '",pod_name="' + pod_name + '"}[' + time_range + '])/1024/1024',
    'memory_usage_day_max': 'max_over_time(container_memory_usage_bytes{image!="",container_name!="POD",namespace="' + project_name + '",pod_name="' + pod_name + '"}[' + time_range + '])/1024/1024',
    'memory_limit': 'kube_pod_container_resource_limits_memory_bytes{namespace="' + project_name + '",pod="' + pod_name + '"}/1024/1024'
  }
  logging.debug('query_list: %s', query_list)

  for query_name in query_list.keys():
    data[query_name] = prom.custom_query(query_list[query_name])
  return data


def create_csv_report():
  logging.info('Create CSV Report')
  for pod in report_files['temp'].keys():
    for container in report_files['temp'][pod]:
      try:
        container_data = report_files['temp'][pod][container]
        report_files['csv_file']['data'].append(
          str(container_data['container_namespace']) + ';' +
          str(container_data['container_node']) + ';' +
          str(container_data['container_pod']) + ';' +
          str(container_data['container_name']) + ';' +
          str(container_data['cpu_request']) + ';' +
          str(container_data['cpu_usage_day']) + ';' +
          str(container_data['cpu_usage_day_max']) + ';' +
          str(container_data['cpu_limit']) + ';' +
          str(round(container_data['memory_request'])) + ';' +
          str(round(container_data['memory_usage_day'])) + ';' +
          str(round(container_data['memory_usage_day_max'])) + ';' +
          str(round(container_data['memory_limit']))
        )
      except Exception as error:
        print()
        logging.error("*********** Error on POD: %s - Container: %s ***********", pod, container)
        logging.exception("Error occurred: %s: %s", type(error).__name__, error)
        print()
        logging.error("Container Data:\n%s", container_data)
        logging.error("*********************************************\n\n")


def main():
  logging.info('Get Pod List')
  v1_pod = dyn_client.resources.get(api_version="v1", kind="Pod")
  pod_list = v1_pod.get(namespace=args.select_namespace)

  for pod in pod_list.items:
    # Set Namespace
    pod_controller = None
    project_name = pod.metadata.namespace
    pod_name = pod.metadata.name
    logging.info('Process Namespace: %s - Pod %s', project_name, pod_name)
    if project_name in exclude_projects:
      logging.info('Skip Namespace: %s', project_name)
      continue

    # Discover POD Controller (DA FINIRE)
    # pod_app_name_label = pod.metadata.labels.get('app.kubernetes.io/name')
    # print(pod_app_name_label)
    # if pod_app_name_label is not None:
    #   v1_deploy = dyn_client.resources.get(api_version="extensions/v1beta1", kind="Deployment")
    #   pod_controller = v1_deploy.get(namespace=project_name, label_selector='app.kubernetes.io/name=' + pod_app_name_label)
    # else:
    #   pod_app_name_label = pod.metadata.labels.get('deploymentconfig')

    # v1_dc = dyn_client.resources.get(api_version="apps.openshift.io/v1", kind="DeploymentConfig")
    # v1_sts = dyn_client.resources.get(api_version="apps/v1", kind="StatefulSet")

    # if len(pod_controller.items) == 1:
    #   print(pod_controller.items[0]['kind'] + '/' + pod_controller.items[0]['metadata']['name'])


    pod_data = get_pod_cpu_memory_usage(project_name,pod_name)
    logging.debug('pod_data:\n%s', pod_data)

    for return_query in pod_data.keys():
      logging.debug('Process Query Name: %s', return_query)
      for container_data in pod_data[return_query]:
        logging.debug('Process container_data: %s', container_data)

        # Set container_name
        if 'container' in container_data['metric'].keys():
          container_name = container_data['metric']['container']
        else:
          container_name = container_data['metric']['container_name']
        logging.debug('Process container_name: %s', container_name)

        # Add pod_name in Report -> temp
        if pod_name not in report_files['temp'].keys():
          report_files['temp'][pod_name] = {}

        # Add container_name in Report -> temp -> pod_name
        if container_name not in report_files['temp'][pod_name].keys():
          logging.debug("Add Container: %s to Temp Report", container_name)
          report_files['temp'][pod_name][container_name] = {
              'container_name': container_name,
              'container_namespace': container_data['metric'].get('namespace'),
              'container_node': container_data['metric'].get('node'),
              'container_pod': pod_name
            }

        # Add return_query in Report -> temp -> pod_name -> container_name
        logging.debug("Add Query: %s to Container Report: %s", return_query, container_name)
        report_files['temp'][pod_name][container_name][return_query] = round(float(container_data['value'][1]),2)
      # logging.debug("report_files['temp']:\n%s", report_files['temp'])

  # Create CSV Report
  create_csv_report()
  logging.info('Final CSV report: \n' + "\n".join(report_files['csv_file']['data']) + "\n")


if __name__ == "__main__":
    main()
