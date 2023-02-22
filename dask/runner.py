import argparse
import json
import os
import sys
import time

import numpy as np
import uproot
from coffea import nanoevents, processor
from rich import pretty

# Make this script work from current directory
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


def validate(file):
    try:
        fin = uproot.open(file)
        return fin["Events"].num_entries
    except RuntimeError:
        print(f"Corrupted file: {file}")
        return


def validation(args, sample_dict):
    start = time.time()
    from p_tqdm import p_map

    all_invalid = []
    for sample in sample_dict.keys():
        _rmap = p_map(
            validate,
            sample_dict[sample],
            num_cpus=args.workers,
            desc=f"Validating {sample[:20]}...",
        )
        _results = list(_rmap)
        counts = np.sum([r for r in _results if np.isreal(r)])
        all_invalid += [r for r in _results if type(r) == str]
        print("Events:", np.sum(counts))
    print("Bad files:")
    for fi in all_invalid:
        print(f"  {fi}")
    end = time.time()
    print("TIME:", time.strftime("%H:%M:%S", time.gmtime(end - start)))
    if input("Remove bad files? (y/n)") == "y":
        print("Removing:")
        for fi in all_invalid:
            print(f"Removing: {fi}")
            os.system(f"rm {fi}")
    sys.exit(0)


def loadder(args):
    with open(args.samplejson) as f:
        sample_dict = json.load(f)
    for key in sample_dict.keys():
        sample_dict[key] = sample_dict[key][: args.limit]
    if args.executor == "dask/casa":
        for key in sample_dict.keys():
            print(key)
            sample_dict[key] = [
                path.replace("xrootd.cmsaf.mit.edu", "xcache")
                for path in sample_dict[key]
            ]
    return sample_dict


def check_port(port):
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
        available = True
    except RuntimeError:
        available = False
    sock.close()
    return available


def get_main_parser():
    parser = argparse.ArgumentParser(
        description="Run analysis on baconbits files using processor coffea files"
    )
    # Inputs
    parser.add_argument(
        "--wf",
        "--workflow",
        dest="workflow",
        choices=["SUEP"],
        help="Which processor to run",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Prefix for the output file name. The file name will have the form: <prefix>_<sample>.hdf5. (default: %(default)s)",
        required=False,
    )
    parser.add_argument(
        "--samples",
        "--json",
        dest="samplejson",
        default="filelist/SUEP_files_simple.json",
        help="JSON file containing dataset and file locations (default: %(default)s)",
    )

    # Scale out
    parser.add_argument(
        "--executor",
        choices=[
            "iterative",
            "futures",
            "parsl/slurm",
            "parsl/condor",
            "dask/condor",
            "dask/slurm",
            "dask/lpc",
            "dask/lxplus",
            "dask/mit",
            "dask/casa",
        ],
        default="futures",
        help="The type of executor to use (default: %(default)s). Other options can be implemented. "
        "For example see https://parsl.readthedocs.io/en/stable/userguide/configuring.html"
        "- `parsl/slurm` - tested at DESY/Maxwell"
        "- `parsl/condor` - tested at DESY, RWTH"
        "- `dask/slurm` - tested at DESY/Maxwell"
        "- `dask/condor` - tested at DESY, RWTH"
        "- `dask/lpc` - custom lpc/condor setup (due to write access restrictions)"
        "- `dask/lxplus` - custom lxplus/condor setup (due to port restrictions)"
        "- `dask/mit` - custom mit/condor setup",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=12,
        help="Number of workers (cores/threads) to use for multi-worker executors "
        "(e.g. futures or condor) (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--scaleout",
        type=int,
        default=1,
        help="Number of nodes to scale out to if using slurm/condor. Total number of "
        "concurrent threads is ``workers x scaleout`` (default: %(default)s)",
    )
    parser.add_argument(
        "--max-scaleout",
        dest="max_scaleout",
        type=int,
        default=250,
        help="The maximum number of nodes to adapt the cluster to. (default: %(default)s)",
    )
    parser.add_argument(
        "--voms",
        default=None,
        type=str,
        help="Path to voms proxy, accessible to worker nodes. By default a copy will be made to $HOME.",
    )
    # Debugging
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Do not process, just check all files are accessible",
    )
    parser.add_argument("--skipbadfiles", action="store_true", help="Skip bad files.")
    parser.add_argument(
        "--only", type=str, default=None, help="Only process specific dataset or file"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Limit to the first N files of each dataset in sample JSON",
    )
    parser.add_argument(
        "--chunk",
        type=int,
        default=15000,
        metavar="N",
        help="Number of events per process chunk",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        metavar="N",
        help="Max number of chunks to run in total",
    )
    parser.add_argument(
        "--isMC", type=int, default=1, help="Specify if the file is MC or data"
    )
    parser.add_argument("--era", type=str, default="2018", help="Specify the year")
    parser.add_argument(
        "--doSyst", type=int, default=1, help="Turn systematics on or off"
    )
    parser.add_argument(
        "--scouting", action="store_true", help="Turn processing for scouting on"
    )
    parser.add_argument("--doInf", action="store_true", help="Turn inference on")
    parser.add_argument("--dataset", type=str, help="Dataset to find xsection")
    parser.add_argument(
        "--trigger", type=str, default="PFHT", help="Specify HLT trigger path"
    )
    parser.add_argument("--skimmed", action="store_true", help="Use skimmed files")
    parser.add_argument("--debug", action="store_true", help="Turn debugging on")
    parser.add_argument("--verbose", action="store_true", help="Turn verbose on")
    return parser


def specificProcessing(args, sample_dict):
    if args.only in sample_dict.keys():  # is dataset
        sample_dict = dict([(args.only, sample_dict[args.only])])
    if "*" in args.only:  # wildcard for datasets
        _new_dict = {}
        print("Will only process the following datasets:")
        for k, v in sample_dict.items():
            if k.lstrip("/").startswith(args.only.rstrip("*")):
                print("    ", k)
                _new_dict[k] = v
        sample_dict = _new_dict
    else:  # is file
        for key in sample_dict.keys():
            if args.only in sample_dict[key]:
                sample_dict = dict([(key, [args.only])])
    return sample_dict


def parslExecutor(args, env_extra, condor_extra):
    import parsl
    from parsl.addresses import address_by_hostname, address_by_query
    from parsl.channels import LocalChannel
    from parsl.config import Config
    from parsl.executors import HighThroughputExecutor
    from parsl.launchers import SrunLauncher
    from parsl.providers import CondorProvider, SlurmProvider

    if "slurm" in args.executor:
        htex_config = Config(
            executors=[
                HighThroughputExecutor(
                    label="coffea_parsl_slurm",
                    address=address_by_hostname(),
                    prefetch_capacity=0,
                    provider=SlurmProvider(
                        channel=LocalChannel(script_dir="logs_parsl"),
                        launcher=SrunLauncher(),
                        max_blocks=(args.scaleout) + 10,
                        init_blocks=args.scaleout,
                        partition="all",
                        worker_init="\n".join(env_extra),
                        walltime="00:120:00",
                    ),
                )
            ],
            retries=20,
        )
    elif "condor" in args.executor:
        htex_config = Config(
            executors=[
                HighThroughputExecutor(
                    label="coffea_parsl_condor",
                    address=address_by_query(),
                    # max_workers=1,
                    provider=CondorProvider(
                        nodes_per_block=1,
                        init_blocks=1,
                        max_blocks=1,
                        worker_init="\n".join(env_extra + condor_extra),
                        walltime="00:20:00",
                    ),
                )
            ]
        )
    else:
        raise NotImplementedError

    parsl.load(htex_config)

    executor = processor.ParslExecutor(config=htex_config)
    return executor


def daskExecutor(args, env_extra):
    import shutil

    from dask_jobqueue import HTCondorCluster, SLURMCluster
    from distributed.diagnostics.plugin import UploadDirectory

    from dask.distributed import Client, Worker, WorkerPlugin

    if "lpc" in args.executor:
        from lpcjobqueue import LPCCondorCluster

        cluster = LPCCondorCluster(
            transfer_input_files="/srv/workflows/",
            shared_temp_directory="/tmp",
            worker_extra_args=[
                "--worker-port 10000:10070",
                "--nanny-port 10070:10100",
                "--no-dashboard",
            ],
            job_script_prologue=[],
            scheduler_options={"dashboard_address": ":44890"},
        )
        cluster.adapt(minimum=args.scaleout, maximum=args.max_scaleout)
        client = Client(cluster)

        class SettingSitePath(WorkerPlugin):
            def setup(self, worker: Worker):
                sys.path.insert(0, os.getcwd() + "/workflows/")

        client.register_worker_plugin(UploadDirectory(os.getcwd() + "/data"))
        client.register_worker_plugin(SettingSitePath())
        shutil.make_archive("workflows", "zip", base_dir="workflows")
        client.upload_file("workflows.zip")
        print("Waiting for at least one worker...")
        client.wait_for_workers(1)
    elif "casa" in args.executor:

        class SettingSitePath(WorkerPlugin):
            def setup(self, worker: Worker):
                sys.path.insert(0, os.getcwd() + "/dask-worker-space/")

        client = Client("tls://localhost:8786")
        client.register_worker_plugin(UploadDirectory(os.getcwd() + "/data"))
        client.register_worker_plugin(SettingSitePath())
        shutil.make_archive("workflows", "zip", base_dir="workflows")
        client.upload_file("workflows.zip")
    elif "lxplus" in args.executor:
        # NOTE: This is unmaintained, but kept for reference
        n_port = 8786
        if not check_port(8786):
            raise RuntimeError(
                "Port '8786' is not occupied on this node. Try another one."
            )
        import socket

        cluster = HTCondorCluster(
            cores=1,
            memory="4GB",  # hardcoded
            disk="1GB",
            death_timeout="60",
            nanny=False,
            scheduler_options={"port": n_port, "host": socket.gethostname()},
            job_extra={
                "log": "dask_out/dask_job_output.log",
                "output": "dask_out/dask_job_output.out",
                "error": "dask_out/dask_job_output.err",
                "should_transfer_files": "Yes",
                "when_to_transfer_output": "ON_EXIT",
                "+SingularityImage": '"/cvmfs/unpacked.cern.ch/registry.hub.docker.com/coffeateam/coffea-dask-cc7:latest"',
                "+JobFlavour": '"workday"',
            },
            extra=[f"--worker-port {n_port}"],
            env_extra=env_extra,
        )
    elif "mit" in args.executor:
        # NOTE: This is unmaintained, but kept for reference
        # n_port = 8786
        # if not check_port(8786):
        #    raise RuntimeError("Port '8786' is not occupied on this node. Try another one.")
        import socket

        cluster = HTCondorCluster(
            cores=1,
            memory="4GB",  # hardcoded
            disk="1GB",
            death_timeout="60",
            nanny=False,
            scheduler_options={
                # 'port': n_port,
                "dashboard_address": 8000,
                "host": socket.gethostname(),
            },
            job_extra={
                "log": "dask_out/dask_job_output.log",
                "output": "dask_out/dask_job_output.out",
                "error": "dask_out/dask_job_output.err",
                "should_transfer_files": "Yes",
                "when_to_transfer_output": "ON_EXIT",
                "+SingularityImage": '"/cvmfs/unpacked.cern.ch/registry.hub.docker.com/coffeateam/coffea-dask-cc7:latest"',
            },
            # extra = ['--worker-port {}'.format(n_port)],
            env_extra=env_extra,
        )
    elif "slurm" in args.executor:
        # NOTE: This is unmaintained, but kept for reference
        cluster = SLURMCluster(
            queue="all",
            cores=args.workers,
            processes=args.workers,
            memory="200 GB",
            retries=10,
            walltime="00:30:00",
            env_extra=env_extra,
        )
    elif "condor" in args.executor:
        # NOTE: This is unmaintained, but kept for reference
        cluster = HTCondorCluster(
            cores=args.workers,
            memory="4GB",
            disk="4GB",
            env_extra=env_extra,
        )
    else:
        raise NotImplementedError(f"I don't know anything about {args.executor}.")

    executor = processor.DaskExecutor(client=client)
    return executor


def nativeExecutors(args):
    executor = processor.IterativeExecutor()
    if args.executor == "futures":
        executor = processor.FuturesExecutor(workers=args.workers)
    return executor


def getWeights(sample_dict):
    from workflows.GenSumWeightExtract import GenSumWeightExtractor

    genSumW_instance = GenSumWeightExtractor()
    genSumW_executor = processor.IterativeExecutor()
    genSumW_run = processor.Runner(
        executor=genSumW_executor,
        schema=nanoevents.BaseSchema,
        align_clusters=True,
    )
    genSumW = genSumW_run(
        fileset=sample_dict,
        treename="Runs",
        processor_instance=genSumW_instance,
    )
    return genSumW


def exportCert(args):
    """
    dask/parsl needs to export x509 to read over xrootd
    dask/lpc uses custom jobqueue provider that handles x509
    """
    if args.voms is not None:
        _x509_path = args.voms
    else:
        try:
            _x509_localpath = (
                [
                    line
                    for line in os.popen("voms-proxy-info").read().split("\n")
                    if line.startswith("path")
                ][0]
                .split(":")[-1]
                .strip()
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "x509 proxy could not be parsed, try creating it with 'voms-proxy-init'"
            ) from exc
        _x509_path = os.environ["HOME"] + f'/.{_x509_localpath.split("/")[-1]}'
        os.system(f"cp {_x509_localpath} {_x509_path}")

    env_extra = [
        "export XRD_RUNFORKHANDLER=1",
        "export XRD_STREAMTIMEOUT=10",
        f"export X509_USER_PROXY={_x509_path}",
        f'export X509_CERT_DIR={os.environ["X509_CERT_DIR"]}',
        f"export PYTHONPATH=$PYTHONPATH:{os.getcwd()}",
    ]
    condor_extra = [
        f'source {os.environ["HOME"]}/.bashrc',
    ]
    return env_extra, condor_extra


def setupSUEP(args, sample_dict):
    """
    Setup the SUEP workflow
    """
    from workflows.SUEP_coffea import SUEP_cluster

    instance = SUEP_cluster(
        isMC=args.isMC,
        era=int(args.era),
        do_syst=1,
        syst_var="",
        sample=sample_dict,
        weight_syst="",
        flag=False,
        scouting=args.scouting,
        do_inf=args.doInf,
        output_location=os.getcwd(),
        accum=args.executor,
        trigger=args.trigger,
        debug=args.debug,
    )
    return instance


def execute(args, processor_instance, sample_dict, env_extra, condor_extra):
    """
    Main function to execute the workflow
    """
    if args.executor in ["futures", "iterative"]:
        executor = nativeExecutors(args)
    elif "parsl" in args.executor:
        executor = parslExecutor(args, env_extra, condor_extra)
    elif "dask" in args.executor:
        executor = daskExecutor(args, env_extra)
    else:
        raise NotImplementedError

    run = processor.Runner(
        executor=executor,
        chunksize=args.chunk,
        maxchunks=args.max,
        schema=nanoevents.NanoAODSchema,
        skipbadfiles=args.skipbadfiles,
    )
    output = run(
        fileset=sample_dict,
        treename="Events",
        processor_instance=processor_instance,
    )

    return output


def saveOutput(args, output, sample, gensumweight=None):
    """
    Save the output to file(s)
    Will calculate weights if necessary
    """
    from workflows import pandas_utils

    if gensumweight is not None:
        output["gensumweight"].value = gensumweight

    df = output["vars"].value

    metadata = dict(
        gensumweight=gensumweight,
        era=processor_instance.era,
        mc=processor_instance.isMC,
        sample=sample,
    )

    # Save the output
    outputName = ""
    if args.output is not None:
        outputName = f"{args.output}_"
    outputName = f"{outputName}{sample}.hdf5"
    print(f"Saving the following output to {outputName}")
    pandas_utils.save_dfs([df], ["vars"], f"{outputName}", metadata=metadata)


if __name__ == "__main__":
    parser = get_main_parser()
    args = parser.parse_args()
    # if args.output == parser.get_default("output"):
    #    args.output = f'{args.workflow}_{(args.samplejson).rstrip(".json")}.hdf5'

    # Load dataset
    sample_dict = loadder(args)

    # For debugging
    # NOTE: This has not been maintained for a while
    if args.only:
        sample_dict = specificProcessing(args, sample_dict)

    # Scan if files can be opened
    # NOTE: This has not been maintained for a while
    if args.validate:
        validation(args, sample_dict)

    # Load workflow
    if args.workflow == "SUEP":
        processor_instance = setupSUEP(args, sample_dict)
    else:
        raise NotImplementedError

    # Setup x509 for dask/parsl
    env_extra, condor_extra = None, None
    if args.executor not in ["futures", "iterative", "dask/lpc", "dask/casa"]:
        env_extra, condor_extra = exportCert(args)

    # Execute the workflow
    output = execute(args, processor_instance, sample_dict, env_extra, condor_extra)

    # Calculate the gen sum weight for skimmed samples
    if args.skimmed:
        weights = getWeights(sample_dict)
        print(
            "You are using skimmed data! I was able to retrieve the following gensum weights:\n"
        )
        pretty.pprint(weights)

    # Save the output
    for sample in sample_dict:
        if args.skimmed:
            saveOutput(args, output[sample], sample, weights[sample].value)
        else:
            saveOutput(args, output[sample], sample)
    if args.verbose:
        pretty.pprint(output)