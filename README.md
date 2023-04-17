# Get Container Requests, Limit and CPU and RAM usage
Collects information about Requests, Limit and CPU and RAM usage for all containers present on the OCP cluster. You can limit of the Namespace with -n option

A CSV will be generated in standard output with the following headers:
 - Namespace
 - Node
 - POD
 - ContainerName
 - CPU_Request(m)
 - CPU_UsageAVG(m)
 - CPU_UsageMAX(m)
 - CPU_Limit(m)
 - Memory_Request(Mi)
 - Memory_UsageAVG(Mi)
 - Memory_UsageMAX(Mi)
 - Memory_Limit(Mi)


## Prerequisites
- Python 3
- [prometheus_api_client](https://pypi.org/project/prometheus-api-client/)
- [openshift](https://pypi.org/project/openshift/)
- [kubernetes](https://pypi.org/project/kubernetes/)


## Examples

- Default collection on all namespaces
  ```bash
  $ python3 get_container_usage_request_limit.py
  ```

- Collecting on a specific namespace via the **-n** option
  ```bash
  $ python3 get_container_usage_request_limit.py -n <NAMESPACE>
  ```

>**N.B You may find memory values different from those set in the pod's yaml file, this is because you need to check the unit of measurement set in the resources.request.memory field.
The correct unit of measurement is Mi (1024) and M (1000). The prometheus query is always executed in Mi (1024).**
