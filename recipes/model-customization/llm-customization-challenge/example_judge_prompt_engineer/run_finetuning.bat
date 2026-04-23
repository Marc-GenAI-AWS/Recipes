@echo off
echo ================================================
echo SageMaker Fine-tuning Setup
echo ================================================

echo.
echo Checking AWS setup...
python check_aws_setup.py

echo.
echo.
echo Starting SageMaker fine-tuning...
python sagemaker_finetune_training.py

echo.
echo Done! Check the output above for results.
pause
