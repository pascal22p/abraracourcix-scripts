<?php
error_reporting(0);

$data = trim(file_get_contents('php://input'));

if(empty($data)) {
  error_log("no content provided");
  echo("no content provided");
  http_response_code(400);
  exit();
}

$metrics = explode("\n", $data);

$fp = fsockopen("tcp://127.0.0.1", 2003, $errno, $errstr);
if (!empty($errno) || !empty($errstr)) {
  error_log(sprintf("%d - %s", $errno, $errstr));
  http_response_code(500);
  exit();
}

foreach($metrics as $data) {
  if (strpos($data, "***REMOVED***")===false) {
    error_log("Not authorised: " . $data);
    http_response_code(401);
    exit();
  } else {
    $data = str_replace("***REMOVED***", "", $data);
  }
     
  $pieces = explode(" ", trim($data));

  if (count($pieces) == 2) {
    $data = trim($data)." ".time().PHP_EOL;
  } else {
    $data = trim($data).PHP_EOL;
  }

  try {
      $bytes = fwrite($fp, $data);
      fflush($fp);
      if($bytes == strlen($data)) {
        echo $data;
      } else {
        error_log("Size does not match");
        http_response_code(500);
        exit();
      }
  } catch (Exception $e) {
    error_log("Network error: ".$e->getMessage());
    http_response_code(500);
    exit();
  }
}

fclose($fp);
http_response_code(202);
?>
