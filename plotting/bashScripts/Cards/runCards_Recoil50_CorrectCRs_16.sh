#!/bin/bash

python datacardMaker.py ZH/samples_withSF_nocuts_UL16.py ZH/systs_fullcorr.py /eos/user/g/gdecastr/SUEPCoffea_dask/Cards/Recoil50_CorrectCRs_Replay/2016 --rootfile /eos/user/g/gdecastr/SUEPCoffea_dask/Plots/Recoil50_16/leadclustertracks --var leadclustertracks --ABCD --year 2016 --region SR --doAll --floatB ;
wait

python datacardMaker.py ZH/samples_withSF_nocuts_UL16.py ZH/systs_fullcorr.py /eos/user/g/gdecastr/SUEPCoffea_dask/Cards/Recoil50_CorrectCRs_Replay/2016 --rootfile /eos/user/g/gdecastr/SUEPCoffea_dask/Plots/Recoil50_CRDY_16/leadclustertracks --var leadclustertracks --ABCD --year 2016 --region CRDY --doAll --floatB ;
wait

python datacardMaker.py ZH/samples_withSF_nocuts_UL16.py ZH/systs_fullcorr.py /eos/user/g/gdecastr/SUEPCoffea_dask/Cards/Recoil50_CorrectCRs_Replay/2016 --rootfile /eos/user/g/gdecastr/SUEPCoffea_dask/Plots/Recoil50_CRTT_16/leadclustertracks --var leadclustertracks --ABCD --year 2016 --region CRTT --doAll --floatB ;
wait