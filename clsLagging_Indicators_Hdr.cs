using System;
using System.Data;
using System.Configuration;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using System.Globalization;
using System.Text;
using EBS_Common.Classes;

namespace EBS.Classes
{
    /// <summary>
    /// Summary description for clsLagging_Indicators_Hdr
    /// </summary>
    public class clsLagging_Indicators_Hdr : EBS_Common.Classes.clsCommonTableFields // inheriting common fields
    {
        #region Defining Local Variables - Class Level
        private SqlConnection Conn;
        private string strConnString = "";
        #endregion

        # region Defining Property Variables


        #region Property Variables Header
        private Int16? _Lagging_Indicator_Id;
        private Int16 _Company_Id;
        private Int16 _Rig_Id;        
        private string _Report_No;        
        private string _Period;
        #endregion

       
        #endregion

        #region Constructor

        public clsLagging_Indicators_Hdr(string constr)
        {
            strConnString = constr;
            Conn = new SqlConnection(strConnString);
        }

        #endregion

        #region Property Declarations Header

        public Int16?  Lagging_Indicator_Id
        {
            get
            {
                return _Lagging_Indicator_Id;
            }
            set
            {
                _Lagging_Indicator_Id = value;
            }
        }

        public Int16 Rig_Id
        {
            get
            {
                return _Rig_Id;
            }
            set
            {
                _Rig_Id = value;
            }
        }

        public Int16 Company_Id
        {
            get
            {
                return _Company_Id;
            }
            set
            {
                _Company_Id = value;
            }
        }       

        public string Report_No
        {
            get
            {
                return _Report_No;
            }
            set
            {
                _Report_No = value;
            }
        }

        public string Period
        {
            get
            {
                return _Period;
            }
            set
            {
                _Period = value;
            }
        }
        #endregion

       

        public void InsertMe()
        {
            SqlTransaction trDML;
            SqlCommand CmdDML;
            StringBuilder strSql = new StringBuilder("");
            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {

                CmdDML = new SqlCommand(OI.Def + "Prc_Lagging_Indicators_Hdr", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                ///For the First time Entry in Header this will have Empty so Insert record in the Lagging_Indicators_Hdr table
                if (!_Lagging_Indicator_Id.HasValue)
                {
                    #region Lagging_Indicators_Hdr
                    
                    CmdDML.Parameters.Add(new SqlParameter("Lagging_Indicator_Id", SqlDbType.SmallInt));
                    CmdDML.Parameters["Lagging_Indicator_Id"].Direction = ParameterDirection.Output;  //Required afterward 


                    CmdDML.Parameters.Add("Company_Id", System.Data.SqlDbType.SmallInt).Value = _Company_Id;
                    CmdDML.Parameters.Add("Rig_Id", System.Data.SqlDbType.SmallInt).Value = _Rig_Id;

                    CmdDML.Parameters.Add("Report_No", System.Data.SqlDbType.VarChar).Value = _Report_No;
                    CmdDML.Parameters.Add("Period", System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(_Period, "dd/MM/yyyy", null));

                    CmdDML.Parameters.Add("Cr_User_Id", System.Data.SqlDbType.SmallInt).Value = Cr_User_Id;
                    CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Insert";
                    CmdDML.ExecuteNonQuery();
                    #endregion

                    if (!string.IsNullOrEmpty(CmdDML.Parameters["Lagging_Indicator_Id"].Value.ToString()))
                    {

                        _Lagging_Indicator_Id = Convert.ToInt16(CmdDML.Parameters["Lagging_Indicator_Id"].Value.ToString());
                    }
                    else
                    {
                        throw new Exception(ErrorString);
                    }


                }
                 
                trDML.Commit();


            }
            catch (SqlException Sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }

        public void DeleteMe()
        {
            ErrorString = "Deletion is not allowed";
            return;
        }

        public void UpdateMe(DataTable DtLagging_Indicators)
        {
            SqlTransaction trDML;
            SqlCommand CmdDML;
            StringBuilder strSql = new StringBuilder("");
            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {

                #region Update Lagging_Indicators details
                if (DtLagging_Indicators != null)
                {
                    for (int intRow = 0; intRow < DtLagging_Indicators.Rows.Count; intRow++)
                    {
                        Int16 intLagging_Indicator_Dtl_Id = Convert.ToInt16(DtLagging_Indicators.Rows[intRow]["Lagging_Indicator_Dtl_Id"].ToString());


                        int intTotal_Count = Convert.ToByte((DtLagging_Indicators.Rows[intRow]["Total_Count"].ToString() == "" ? 0.ToString() : DtLagging_Indicators.Rows[intRow]["Total_Count"].ToString()));
                        string strActive= DtLagging_Indicators.Rows[intRow]["Active"].ToString();
                        
                        CmdDML = new SqlCommand(OI.Def + "Prc_Lagging_Indicators_Hdr", Conn, trDML);
                        CmdDML.CommandType = CommandType.StoredProcedure;

                        CmdDML.Parameters.Add("Lagging_Indicator_Dtl_Id", System.Data.SqlDbType.Int).Value = intLagging_Indicator_Dtl_Id;

                        CmdDML.Parameters.Add("Total_Count", System.Data.SqlDbType.TinyInt).Value = intTotal_Count;
                         
                        CmdDML.Parameters.Add("Active", System.Data.SqlDbType.VarChar).Value = strActive;

                        CmdDML.Parameters.Add("Mod_User_Id", System.Data.SqlDbType.SmallInt).Value = Mod_User_Id;
                        CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Update";
                        CmdDML.ExecuteNonQuery();

                    }
                }
                #endregion
                trDML.Commit();

            }
            catch (SqlException Sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }
    }
}
